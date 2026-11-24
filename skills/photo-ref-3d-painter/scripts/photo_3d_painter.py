"""
Photo-Reference 3D Print Painter — Reusable Blender Python Library
==================================================================
Import inside Blender MCP `execute_blender_code`:

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path.home() / ".gemini/config/skills/photo-ref-3d-painter/scripts"))
    import photo_3d_painter as p3p

Zero external pip dependencies: uses Blender's native bpy.data.images, bmesh,
mathutils.bvhtree, numpy, zipfile, and xml.etree.
"""

import math
import os
import zipfile
from collections import deque, defaultdict
import numpy as np
import bpy
import bmesh
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree


# =============================================================================
# 1. IMAGE LOADING & FOREGROUND CROP DETECTION
# =============================================================================

def load_image_rgb(filepath):
    """
    Load an image via Blender's native image loader and return a float32 numpy array
    of shape (H, W, 3) in [0, 1] sRGB, where row 0 is the BOTTOM of the image (v=0)
    and row H-1 is the TOP of the image (v=1).
    """
    img = bpy.data.images.load(filepath, check_existing=False)
    w, h = img.size[0], img.size[1]
    rgba = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
    rgb = rgba[:, :, :3].copy()
    alpha = rgba[:, :, 3].copy()
    bpy.data.images.remove(img)
    return rgb, alpha


def auto_detect_subject_crop(rgb, alpha=None, pad_frac=0.01):
    """
    Detect tight normalized UV bounding box (u_min, u_max, v_min, v_max) of the
    foreground subject in a clean isolated photo (transparent PNG or uniform border bg).
    """
    h, w, _ = rgb.shape
    if alpha is not None and alpha.min() < 0.95:
        mask = alpha > 0.25
    else:
        # Estimate background color from the 4 corner patches
        corners = np.concatenate([
            rgb[:16, :16].reshape(-1, 3),
            rgb[:16, -16:].reshape(-1, 3),
            rgb[-16:, :16].reshape(-1, 3),
            rgb[-16:, -16:].reshape(-1, 3),
        ], axis=0)
        bg_med = np.median(corners, axis=0)
        diff = np.linalg.norm(rgb - bg_med[None, None, :], axis=2)
        mask = diff > 0.12

    ys, xs = np.where(mask)
    if len(xs) < 10:
        return (0.0, 1.0, 0.0, 1.0)
    u0 = max(0.0, xs.min() / w - pad_frac)
    u1 = min(1.0, xs.max() / w + pad_frac)
    v0 = max(0.0, ys.min() / h - pad_frac)
    v1 = min(1.0, ys.max() / h + pad_frac)
    return (float(u0), float(u1), float(v0), float(v1))


# =============================================================================
# 2. SHADOW-RESISTANT CIELAB COLOR SPACE & FILAMENT PALETTE QUANTIZATION
# =============================================================================

def srgb_to_lab(rgb):
    """
    Vectorized sRGB [0..1] (..., 3) -> CIE L*a*b* (D65) in pure numpy.
    L* in [0, 100], a* and b* roughly in [-128, 128].
    """
    rgb = np.clip(np.asarray(rgb, dtype=np.float32), 0.0, 1.0)
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)

    # sRGB linear -> XYZ (D65)
    M = np.array([
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ], dtype=np.float32)
    xyz = lin @ M.T
    # Normalize by D65 white point
    xyz[..., 0] /= 0.95047
    xyz[..., 1] /= 1.00000
    xyz[..., 2] /= 1.08883

    eps = 0.008856
    kappa = 903.3
    f = np.where(xyz > eps, np.cbrt(np.maximum(xyz, 0.0)), (kappa * xyz + 16.0) / 116.0)

    L = 116.0 * f[..., 1] - 16.0
    a = 500.0 * (f[..., 0] - f[..., 1])
    b = 200.0 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


def quantize_rgb_to_palette_lab(
    sample_rgb,
    palette_rgbs,
    chroma_weight=1.35,
    lightness_weight=0.75,
    shadow_white_L=58.0,
    neutral_chroma_max=10.0,
    white_idx=None,
    black_idx=None,
):
    """
    Quantize an (N, 3) array of sampled sRGB pixels to the nearest physical filament
    index in `palette_rgbs` using shadow-resistant weighted CIELAB Delta-E.

    If `white_idx` and `black_idx` are given, neutral pixels (chroma < neutral_chroma_max)
    are split cleanly at `shadow_white_L` so shadowed white plastic never flips to black!
    """
    s_lab = srgb_to_lab(sample_rgb)                      # (N, 3)
    p_lab = srgb_to_lab(np.array(palette_rgbs, dtype=np.float32))  # (K, 3)

    weights = np.array([lightness_weight, chroma_weight, chroma_weight], dtype=np.float32)
    diff = (s_lab[:, None, :] - p_lab[None, :, :]) * weights[None, None, :]
    d2 = np.sum(diff * diff, axis=2)                     # (N, K)
    labels = np.argmin(d2, axis=1).astype(np.int32)

    if white_idx is not None and black_idx is not None and shadow_white_L is not None:
        chroma = np.hypot(s_lab[:, 1], s_lab[:, 2])
        is_neutral = (chroma < neutral_chroma_max) & ((labels == white_idx) | (labels == black_idx))
        labels = np.where(is_neutral & (s_lab[:, 0] >= shadow_white_L), white_idx, labels)
        labels = np.where(is_neutral & (s_lab[:, 0] < shadow_white_L), black_idx, labels)

    return labels


# =============================================================================
# 3. CAMERA PROJECTION, OCCLUSION FILTER, SYMMETRY, BACKFILL & DENOISING
# =============================================================================

def _make_camera_basis(view_dir):
    """
    Build orthonormal right-handed camera basis:
    - fwd = normalized vector pointing FROM model TOWARD camera
    - right = horizontal right vector on the photograph
    - up = vertical up vector on the photograph
    """
    fwd = Vector(view_dir).normalized()
    world_up = Vector((0.0, 0.0, 1.0))
    if abs(fwd.dot(world_up)) > 0.98:
        world_up = Vector((0.0, 1.0, 0.0))
    right = world_up.cross(fwd).normalized()
    up = fwd.cross(right).normalized()
    return right, up, fwd


def _denoise_islands(bm, labels, min_island_faces=35, protect_indices=()):
    """Merge tiny speckled color islands (< min_island_faces) into their longest-border neighbor."""
    if min_island_faces <= 1:
        return labels
    bm.faces.ensure_lookup_table()
    n_f = len(bm.faces)
    visited = np.zeros(n_f, dtype=bool)
    protect = set(protect_indices)

    for start in range(n_f):
        if visited[start]:
            continue
        col = int(labels[start])
        if col < 0 or col in protect:
            visited[start] = True
            continue
        # BFS connected component of same color
        comp = []
        border_counts = defaultdict(int)
        q = deque([start])
        visited[start] = True
        while q:
            fi = q.popleft()
            comp.append(fi)
            f = bm.faces[fi]
            for e in f.edges:
                for nf in e.link_faces:
                    ni = nf.index
                    if ni == fi:
                        continue
                    nc = int(labels[ni])
                    if nc == col:
                        if not visited[ni]:
                            visited[ni] = True
                            q.append(ni)
                    elif nc >= 0:
                        border_counts[nc] += 1
        if len(comp) < min_island_faces and border_counts:
            best_neighbor = max(border_counts.keys(), key=lambda k: border_counts[k])
            for fi in comp:
                labels[fi] = best_neighbor
    return labels


def _smooth_boundaries(bm, labels, passes=2, protect_indices=()):
    """Majority-vote boundary smoothing across adjacent faces."""
    if passes <= 0:
        return labels
    bm.faces.ensure_lookup_table()
    protect = set(protect_indices)
    n_f = len(bm.faces)
    for _ in range(passes):
        new_labels = labels.copy()
        for fi in range(n_f):
            c = int(labels[fi])
            if c in protect or c < 0:
                continue
            counts = defaultdict(int)
            counts[c] += 1
            for e in bm.faces[fi].edges:
                for nf in e.link_faces:
                    if nf.index != fi:
                        nc = int(labels[nf.index])
                        if nc >= 0:
                            counts[nc] += 1
            # Switch only if another color has strict majority among edge neighbors
            best_c = max(counts.keys(), key=lambda k: counts[k])
            if best_c != c and counts[best_c] >= 3 and best_c not in protect:
                new_labels[fi] = best_c
        labels = new_labels
    return labels


def _geodesic_fill_unseen(bm, labels):
    """Multi-source BFS flood-fill from seen faces (>=0) into unseen faces (-1)."""
    bm.faces.ensure_lookup_table()
    q = deque()
    for fi, c in enumerate(labels):
        if c >= 0:
            q.append(fi)
    while q:
        fi = q.popleft()
        col = int(labels[fi])
        for e in bm.faces[fi].edges:
            for nf in e.link_faces:
                ni = nf.index
                if labels[ni] < 0:
                    labels[ni] = col
                    q.append(ni)
    return labels


def make_filament_material(name, rgb, roughness=0.48, coat=0.0):
    mat = bpy.data.materials.get(name)
    if not mat:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        if "Coat Weight" in bsdf.inputs:
            bsdf.inputs["Coat Weight"].default_value = coat
    mat.diffuse_color = (*rgb, 1.0)
    return mat


def project_photo_to_mesh(
    obj,
    img_path,
    palette,
    view_dir=(0.0, -1.0, 0.22),
    canonical_rot_z_deg=0.0,
    crop_uv=None,
    proj_z_range=None,
    perspective_fov_deg=0.0,
    min_facing_dot=0.14,
    chroma_weight=1.35,
    lightness_weight=0.75,
    shadow_white_L=58.0,
    white_name="White",
    black_name="Black",
    symmetry_x=False,
    symmetry_prefer_side=None,
    back_default_name=None,
    back_y_threshold=2.0,
    z_floor_override=None,
    min_island_faces=120,
    smooth_passes=4,
    protect_names=(),
    sample_radius_px=2,
):
    """
    Project colors from a reference photograph `img_path` directly onto `obj`'s faces.

    Parameters:
    - palette: list of dicts [{"name": "White", "rgb": (0.95, 0.95, 0.96), "roughness": 0.48, "coat": 0.0}, ...]
    - view_dir: 3D direction vector (in canonical frame) pointing FROM model TOWARD camera.
    - canonical_rot_z_deg: Z rotation (degrees) applied temporarily to align model to -Y facing (X=0 symmetry).
    - crop_uv: (u_min, u_max, v_min, v_max) of subject in photo (Blender v=0 bottom..1 top). Auto-detected if None.
    - proj_z_range: optional (z_min, z_max) in canonical frame to restrict bbox fitting (e.g., head above box rim!).
    - perspective_fov_deg: 0.0 for orthographic projection (cleanest for aligned product photos), or >0 for perspective.
    - symmetry_x: enforce exact X-mirror symmetry of painted labels in canonical frame.
    - symmetry_prefer_side: "+X", "-X", or None (average/prefer better-facing side when mirroring).
    - back_default_name: optional palette color name for unseen rear faces (y > back_y_threshold).
    - z_floor_override: optional (z_threshold, color_name) to paint hidden lower base/collar uniformly.
    """
    rgb_img, alpha_img = load_image_rgb(img_path)
    img_h, img_w, _ = rgb_img.shape
    if crop_uv is None:
        crop_uv = auto_detect_subject_crop(rgb_img, alpha_img)
    u0, u1, v0, v1 = crop_uv

    names = [p["name"] for p in palette]
    rgbs = [p["rgb"] for p in palette]
    white_idx = names.index(white_name) if white_name in names else None
    black_idx = names.index(black_name) if black_name in names else None
    back_idx = names.index(back_default_name) if back_default_name in names else None
    protect_indices = [names.index(n) for n in protect_names if n in names]

    # Setup materials on object
    obj.data.materials.clear()
    for p in palette:
        mat = make_filament_material(
            f"MAT_Filament_{p['name']}",
            p["rgb"],
            roughness=p.get("roughness", 0.48),
            coat=p.get("coat", 0.0),
        )
        obj.data.materials.append(mat)

    rot_to_canon = Matrix.Rotation(math.radians(canonical_rot_z_deg), 4, 'Z')
    rot_back = Matrix.Rotation(math.radians(-canonical_rot_z_deg), 4, 'Z')

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.transform(bm, matrix=rot_to_canon, verts=bm.verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.faces.ensure_lookup_table()
    bvh = BVHTree.FromBMesh(bm)

    right, up, fwd = _make_camera_basis(view_dir)

    # Compute projected 2D coordinates of vertices (within proj_z_range if given) to align bbox -> crop_uv
    fit_verts = [
        v.co for v in bm.verts
        if proj_z_range is None or (proj_z_range[0] <= v.co.z <= proj_z_range[1])
    ]
    mesh_center = sum(fit_verts, Vector((0, 0, 0))) / max(1, len(fit_verts))
    cam_dist = 180.0
    cam_pos = mesh_center + fwd * cam_dist

    def project_point(pt):
        rel = pt - mesh_center
        px = rel.dot(right)
        py = rel.dot(up)
        if perspective_fov_deg > 1.0:
            depth = max(10.0, cam_dist - rel.dot(fwd))
            scale = cam_dist / depth
            px *= scale
            py *= scale
        return px, py

    proj_pts = [project_point(p) for p in fit_verts]
    px_min = min(p[0] for p in proj_pts)
    px_max = max(p[0] for p in proj_pts)
    py_min = min(p[1] for p in proj_pts)
    py_max = max(p[1] for p in proj_pts)
    px_span = max(1e-5, px_max - px_min)
    py_span = max(1e-5, py_max - py_min)

    # Sample photo pixel for every visible, front-facing face!
    n_f = len(bm.faces)
    labels = np.full(n_f, -1, dtype=np.int32)
    seen_indices = []
    seen_rgbs = []
    face_centers = []
    face_dots = np.zeros(n_f, dtype=np.float32)

    for fi, f in enumerate(bm.faces):
        c = f.calc_center_median()
        face_centers.append(c)
        if proj_z_range is not None and (c.z < proj_z_range[0] or c.z > proj_z_range[1]):
            continue

        # Ray direction toward camera
        to_cam = (cam_pos - c).normalized() if perspective_fov_deg > 1.0 else fwd
        dot = f.normal.dot(to_cam)
        face_dots[fi] = dot
        if dot < min_facing_dot:
            continue

        # BVH self-occlusion test: cast ray slightly off surface toward camera
        hit_loc, _, _, hit_dist = bvh.ray_cast(c + f.normal * 0.03, to_cam, cam_dist)
        if hit_loc is not None:
            continue  # Occluded by another part of the model!

        px, py = project_point(c)
        u = u0 + ((px - px_min) / px_span) * (u1 - u0)
        v = v0 + ((py - py_min) / py_span) * (v1 - v0)
        if u < 0.0 or u > 1.0 or v < 0.0 or v > 1.0:
            continue

        ix = min(img_w - 1, max(0, int(u * (img_w - 1))))
        iy = min(img_h - 1, max(0, int(v * (img_h - 1))))
        seen_indices.append(fi)
        if sample_radius_px > 0:
            r = sample_radius_px
            patch = rgb_img[max(0, iy - r):min(img_h, iy + r + 1), max(0, ix - r):min(img_w, ix + r + 1)]
            seen_rgbs.append(np.median(patch.reshape(-1, 3), axis=0))
        else:
            seen_rgbs.append(rgb_img[iy, ix])

    if seen_rgbs:
        q_labels = quantize_rgb_to_palette_lab(
            np.array(seen_rgbs, dtype=np.float32),
            rgbs,
            chroma_weight=chroma_weight,
            lightness_weight=lightness_weight,
            shadow_white_L=shadow_white_L,
            white_idx=white_idx,
            black_idx=black_idx,
        )
        for fi, lbl in zip(seen_indices, q_labels):
            labels[fi] = int(lbl)

    # Optional exact X-symmetry enforcement (great when photo has slight 3/4 tilt!)
    if symmetry_x:
        # Map every face center to its mirrored face via BVH find_nearest
        mirrored_labels = labels.copy()
        for fi, c in enumerate(face_centers):
            if symmetry_prefer_side == "+X" and c.x < 0:
                m_pt = Vector((-c.x, c.y, c.z))
                _, _, m_idx, _ = bvh.find_nearest(m_pt)
                if m_idx is not None and labels[m_idx] >= 0:
                    mirrored_labels[fi] = labels[m_idx]
            elif symmetry_prefer_side == "-X" and c.x > 0:
                m_pt = Vector((-c.x, c.y, c.z))
                _, _, m_idx, _ = bvh.find_nearest(m_pt)
                if m_idx is not None and labels[m_idx] >= 0:
                    mirrored_labels[fi] = labels[m_idx]
            elif symmetry_prefer_side is None and labels[fi] < 0:
                m_pt = Vector((-c.x, c.y, c.z))
                _, _, m_idx, _ = bvh.find_nearest(m_pt)
                if m_idx is not None and labels[m_idx] >= 0:
                    mirrored_labels[fi] = labels[m_idx]
        labels = mirrored_labels

    # Assign unseen rear faces to back_default_name if requested (e.g., black back of head)
    if back_idx is not None:
        for fi, c in enumerate(face_centers):
            if labels[fi] < 0 and c.y > back_y_threshold:
                labels[fi] = back_idx

    # Optional hidden lower base/collar override (e.g., Z < 6.5 mm)
    if z_floor_override is not None:
        z_lim, z_cname = z_floor_override
        z_cidx = names.index(z_cname)
        for fi, c in enumerate(face_centers):
            if c.z < z_lim:
                labels[fi] = z_cidx

    # Fill any remaining unseen crevices/undersides via geodesic multi-source BFS
    labels = _geodesic_fill_unseen(bm, labels)

    # Denoise speckled islands & smooth boundaries
    labels = _denoise_islands(bm, labels, min_island_faces=min_island_faces, protect_indices=protect_indices)
    labels = _smooth_boundaries(bm, labels, passes=smooth_passes, protect_indices=protect_indices)

    # Apply final material indices back to mesh
    counts = {name: 0 for name in names}
    for fi, f in enumerate(bm.faces):
        mi = max(0, int(labels[fi]))
        f.material_index = mi
        counts[names[mi]] += 1

    bmesh.ops.transform(bm, matrix=rot_back, verts=bm.verts)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    bpy.context.view_layer.update()

    return {
        "crop_uv": crop_uv,
        "seen_faces": len(seen_indices),
        "total_faces": n_f,
        "material_counts": counts,
    }


# =============================================================================
# 4. NATIVE BAMBU STUDIO / ORCASLICER MULTI-COLOR .3MF EXPORTER (PURE PYTHON)
# =============================================================================

def _rgb_to_hex(rgb):
    r, g, b = [min(255, max(0, int(round(c * 255)))) for c in rgb[:3]]
    return f"#{r:02X}{g:02X}{b:02X}FF"


def _bambu_paint_hex(slot_1_based):
    """
    Encode a full-triangle single-extruder slot (1-based) in Bambu Studio / OrcaSlicer
    TriangleSelector `paint_color` hex notation:
      slot 1 -> "4", slot 2 -> "8", slot 3 -> "C", slot 4 -> "1C", slot 5 -> "2C", ...
    For slots 1..3: (slot << 2) -> 4, 8, C. For slots >= 4: ((slot - 3) << 4) | 0xC.
    Note: Slot 1 is usually the object's base filament (unpainted/omitted).
    """
    if slot_1_based <= 1:
        return None
    if slot_1_based == 2:
        return "8"
    if slot_1_based == 3:
        return "C"
    # General Bambu/Prusa 2-nibble encoding for extruder >= 4
    hi = slot_1_based - 3
    return f"{hi:X}C"


def export_multicolor_3mf(
    obj,
    filepath,
    apply_modifiers=True,
    center_z0=True,
    include_bambu_paint_color=True,
):
    """
    Export `obj` as a spec-compliant multi-color `.3mf` archive with `<basematerials>`
    and per-triangle material indices (+ optional Bambu Studio / OrcaSlicer `paint_color`
    attributes). Zero external addons required.
    """
    was_hidden = obj.hide_viewport
    obj.hide_viewport = False
    bpy.context.view_layer.update()

    bm = bmesh.new()
    if apply_modifiers:
        deps = bpy.context.evaluated_depsgraph_get()
        ev = obj.evaluated_get(deps)
        bm.from_mesh(ev.to_mesh())
        ev.to_mesh_clear()
    else:
        bm.from_mesh(obj.data)
    obj.hide_viewport = was_hidden

    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    if center_z0:
        xs = [v.co.x for v in bm.verts]
        ys = [v.co.y for v in bm.verts]
        zs = [v.co.z for v in bm.verts]
        bmesh.ops.transform(
            bm,
            matrix=Matrix.Translation((-(min(xs) + max(xs)) / 2.0, -(min(ys) + max(ys)) / 2.0, -min(zs))),
            verts=bm.verts,
        )
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    nm = sum(1 for e in bm.edges if not e.is_manifold)

    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Collect palette materials from object slots
    mat_entries = []
    for i, m in enumerate(obj.data.materials):
        if m:
            col_hex = _rgb_to_hex(m.diffuse_color[:3])
            mat_entries.append((m.name, col_hex))
        else:
            mat_entries.append((f"Filament_{i+1}", "#CCCCCCFF"))
    if not mat_entries:
        mat_entries = [("Default", "#CCCCCCFF")]

    # Build 3D/3dmodel.model XML efficiently via list join
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">',
        ' <resources>',
        '  <basematerials id="1">',
    ]
    for mname, mhex in mat_entries:
        safe_name = mname.replace('"', "")
        lines.append(f'   <base name="{safe_name}" displaycolor="{mhex}" />')
    lines.append('  </basematerials>')
    lines.append('  <object id="2" type="model" pid="1" pindex="0">')
    lines.append('   <mesh>')
    lines.append('    <vertices>')
    for v in bm.verts:
        lines.append(f'     <vertex x="{v.co.x:.4f}" y="{v.co.y:.4f}" z="{v.co.z:.4f}" />')
    lines.append('    </vertices>')
    lines.append('    <triangles>')
    for f in bm.faces:
        v0, v1, v2 = f.verts[0].index, f.verts[1].index, f.verts[2].index
        mi = min(len(mat_entries) - 1, max(0, f.material_index))
        pc_attr = ""
        if include_bambu_paint_color:
            pc = _bambu_paint_hex(mi + 1)
            if pc:
                pc_attr = f' paint_color="{pc}"'
        lines.append(f'     <triangle v1="{v0}" v2="{v1}" v3="{v2}" pid="1" p1="{mi}"{pc_attr} />')
    lines.append('    </triangles>')
    lines.append('   </mesh>')
    lines.append('  </object>')
    lines.append(' </resources>')
    lines.append(' <build>')
    lines.append('  <item objectid="2" />')
    lines.append(' </build>')
    lines.append('</model>')

    model_xml = "\n".join(lines).encode("utf-8")
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml" />\n'
        ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml" />\n'
        '</Types>\n'
    ).encode("utf-8")
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        ' <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" />\n'
        '</Relationships>\n'
    ).encode("utf-8")

    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with zipfile.ZipFile(filepath, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("3D/3dmodel.model", model_xml)

    n_tris = len(bm.faces)
    bm.free()
    return {
        "filepath": filepath,
        "triangles": n_tris,
        "materials": len(mat_entries),
        "non_manifold": nm,
        "size_kb": round(os.path.getsize(filepath) / 1024.0, 1),
    }

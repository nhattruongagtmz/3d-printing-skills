"""
No-AMS Multi-Color 3D Print Splitter — Reusable Blender Python Library
======================================================================
Import inside Blender MCP `execute_blender_code`:

    import sys; from pathlib import Path
    sys.path.insert(0, str(Path.home() / '.gemini/config/skills/no-ams-color-split/scripts'))
    import no_ams_splitter as nas

All geometry operates in 1 Blender Unit = 1 mm (standard STL print scale).
"""

import math
import os
from collections import defaultdict
import bpy
import bmesh
from mathutils import Vector, Matrix, Euler, geometry
from mathutils.bvhtree import BVHTree


# =============================================================================
# 1. SCENE, COLLECTION & MATERIAL HELPERS
# =============================================================================

def get_or_create_collection(name, parent=None, clear_objects=False):
    col = bpy.data.collections.get(name)
    if not col:
        col = bpy.data.collections.new(name)
        if parent:
            parent.children.link(col)
        else:
            bpy.context.scene.collection.children.link(col)
    elif clear_objects:
        for obj in list(col.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
    return col


def make_pbr_material(name, rgb, roughness=0.50, coat=0.0):
    """Create or update a PBR material with matching viewport solid diffuse_color."""
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


def snapshot_evaluated_bmesh(obj, transform=None):
    """Return a clean, evaluated bmesh copy of `obj` (with all modifiers applied)."""
    was_hidden = obj.hide_viewport
    obj.hide_viewport = False
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    bm = bmesh.new()
    bm.from_mesh(ev.to_mesh())
    ev.to_mesh_clear()
    obj.hide_viewport = was_hidden
    if transform is not None:
        bmesh.ops.transform(bm, matrix=transform, verts=bm.verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def count_non_manifold(bm):
    return sum(1 for e in bm.edges if not e.is_manifold)


def count_loose_verts(bm):
    return sum(1 for v in bm.verts if not v.link_edges)


# =============================================================================
# 2. PRE-SPLIT MESH PREP (MIRROR SYMMETRY + CDT HARMONIC BUMP FLATTENING)
# =============================================================================

def mirror_symmetrize(bm, keep_side="+X", x_mid=0.0, yaw_rad=0.0):
    """
    Symmetrize a -Y-facing bmesh cleanly across X = x_mid.
    Uses tight seam merge (0.0001 mm) + degenerate dissolve so non_manifold == 0.
    """
    if abs(yaw_rad) > 1e-6:
        bmesh.ops.transform(bm, matrix=Matrix.Rotation(-yaw_rad, 4, 'Z'), verts=bm.verts)
    if abs(x_mid) > 1e-6:
        bmesh.ops.transform(bm, matrix=Matrix.Translation((-x_mid, 0.0, 0.0)), verts=bm.verts)

    plane_no = (1.0, 0.0, 0.0) if keep_side == "+X" else (-1.0, 0.0, 0.0)
    bmesh.ops.bisect_plane(
        bm,
        geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
        plane_co=(0.0, 0.0, 0.0),
        plane_no=plane_no,
        dist=1e-5,
        clear_inner=True,
        clear_outer=False,
    )

    geom_orig = bm.verts[:] + bm.edges[:] + bm.faces[:]
    ret = bmesh.ops.duplicate(bm, geom=geom_orig)
    dup_verts = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    dup_faces = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMFace)]
    for v in dup_verts:
        v.co.x = -v.co.x
    bmesh.ops.reverse_faces(bm, faces=dup_faces)

    seam_verts = [v for v in bm.verts if abs(v.co.x) < 0.002]
    bmesh.ops.remove_doubles(bm, verts=seam_verts, dist=0.0001)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return count_non_manifold(bm)


def cdt_harmonic_flatten_front_patch(
    bm,
    cx,
    cz,
    rx,
    rz,
    y_max=-3.5,
    grid_step=0.28,
    harmonic_iters=120,
):
    """
    Remove a folded/protruding sculpt bump on the front (-Y) face inside ellipse (cx, cz, rx, rz),
    fill with uniform 2D Constrained Delaunay Triangulation (zero poles/spokes),
    and relax with pure harmonic Laplacian smoothing so the surface sits 100% flush.
    """
    del_faces = [
        f for f in bm.faces
        if f.calc_center_median().y < y_max
        and math.hypot((f.calc_center_median().x - cx) / rx, (f.calc_center_median().z - cz) / rz) < 1.0
    ]
    if not del_faces:
        return 0
    bmesh.ops.delete(bm, geom=del_faces, context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='VERTS')

    hole_edges = [
        e for e in bm.edges
        if e.is_boundary
        and e.verts[0].co.y < y_max
        and math.hypot((e.verts[0].co.x - cx) / (rx * 1.3), (e.verts[0].co.z - cz) / (rz * 1.3)) < 1.0
    ]
    hole_verts = list({v for e in hole_edges for v in e.verts})
    v_to_idx = {v: i for i, v in enumerate(hole_verts)}
    avg_y = sum(v.co.y for v in hole_verts) / max(1, len(hole_verts))

    pts_2d = [Vector((v.co.x, v.co.z)) for v in hole_verts]
    edges_2d = [(v_to_idx[e.verts[0]], v_to_idx[e.verts[1]]) for e in hole_edges]
    n_bound = len(pts_2d)

    x_cur = cx - rx
    while x_cur <= cx + rx:
        z_cur = cz - rz
        while z_cur <= cz + rz:
            if math.hypot((x_cur - cx) / rx, (z_cur - cz) / rz) < 0.93:
                p = Vector((x_cur, z_cur))
                if all((p - bp).length > grid_step * 0.5 for bp in pts_2d[:n_bound]):
                    pts_2d.append(p)
            z_cur += grid_step
        x_cur += grid_step

    cdt_verts, _, cdt_faces, orig_v, _, _ = geometry.delaunay_2d_cdt(pts_2d, edges_2d, [], 0, 1e-5)

    cdt_bm_verts = []
    interior_verts = []
    for idx, p2 in enumerate(cdt_verts):
        reused = next((hole_verts[oi] for oi in orig_v[idx] if oi < n_bound), None)
        if reused is not None:
            cdt_bm_verts.append(reused)
        else:
            nv = bm.verts.new((p2.x, avg_y, p2.y))
            cdt_bm_verts.append(nv)
            interior_verts.append(nv)

    def inside_poly_2d(px, pz):
        inside = False
        for i0, i1 in edges_2d:
            x0, z0 = pts_2d[i0].x, pts_2d[i0].y
            x1, z1 = pts_2d[i1].x, pts_2d[i1].y
            if ((z0 > pz) != (z1 > pz)) and (px < (x1 - x0) * (pz - z0) / (z1 - z0 + 1e-12) + x0):
                inside = not inside
        return inside

    for f_idxs in cdt_faces:
        if len(f_idxs) != 3:
            continue
        fcx = sum(cdt_verts[i].x for i in f_idxs) / 3.0
        fcz = sum(cdt_verts[i].y for i in f_idxs) / 3.0
        if inside_poly_2d(fcx, fcz):
            fv = [cdt_bm_verts[i] for i in f_idxs]
            if len(set(fv)) == 3:
                try:
                    bm.faces.new(fv)
                except ValueError:
                    pass

    unused = [v for v in interior_verts if not v.link_faces]
    if unused:
        bmesh.ops.delete(bm, geom=unused, context='VERTS')

    # Fill any tiny edge slit left at concave boundary corners
    bmesh.ops.remove_doubles(bm, verts=[v for v in bm.verts if v.is_boundary], dist=0.005)
    b_edges = [e for e in bm.edges if e.is_boundary]
    if b_edges:
        bmesh.ops.holes_fill(bm, edges=b_edges, sides=0)

    # Pure harmonic Laplacian relaxation on the uniform CDT interior + narrow rim -> 100% flush!
    relax_verts = [
        v for v in bm.verts
        if v.is_valid and v.co.y < y_max
        and math.hypot((v.co.x - cx) / (rx * 1.06), (v.co.z - cz) / (rz * 1.06)) < 1.0
    ]
    for _ in range(harmonic_iters):
        bmesh.ops.smooth_vert(bm, verts=relax_verts, factor=0.5, use_axis_x=False, use_axis_y=True, use_axis_z=False)
    for _ in range(10):
        bmesh.ops.smooth_vert(bm, verts=relax_verts, factor=0.35, use_axis_x=True, use_axis_y=True, use_axis_z=True)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return count_non_manifold(bm)


# =============================================================================
# 3. EXACT BOOLEAN ENGINE (SAFE TEMP-OBJECT WRAPPER)
# =============================================================================

def bool_op(bm_a, bm_b, operation='DIFFERENCE', solver='EXACT'):
    """
    Execute a clean Exact Boolean between two bmeshes and return a new bmesh.
    Cleans up temporary objects and datablocks automatically.
    """
    me_a = bpy.data.meshes.new("_nas_a_tmp")
    me_b = bpy.data.meshes.new("_nas_b_tmp")
    bm_a.to_mesh(me_a)
    bm_b.to_mesh(me_b)
    ob_a = bpy.data.objects.new("_nas_a_tmp", me_a)
    ob_b = bpy.data.objects.new("_nas_b_tmp", me_b)
    bpy.context.scene.collection.objects.link(ob_a)
    bpy.context.scene.collection.objects.link(ob_b)

    mod = ob_a.modifiers.new("BOOL", 'BOOLEAN')
    mod.operation = operation
    mod.solver = solver
    mod.object = ob_b
    bpy.context.view_layer.update()

    deps = bpy.context.evaluated_depsgraph_get()
    ev_a = ob_a.evaluated_get(deps)
    bm_res = bmesh.new()
    bm_res.from_mesh(ev_a.to_mesh())
    ev_a.to_mesh_clear()

    bpy.data.objects.remove(ob_a, do_unlink=True)
    bpy.data.objects.remove(ob_b, do_unlink=True)
    if me_a.users == 0:
        bpy.data.meshes.remove(me_a)
    if me_b.users == 0:
        bpy.data.meshes.remove(me_b)

    bmesh.ops.recalc_face_normals(bm_res, faces=bm_res.faces)
    return bm_res


# =============================================================================
# 4. 2D PROFILES, TANGENT FRAMES & SURFACE-CONFORMED INSERT BUILDERS
# =============================================================================

def make_tangent_frame(normal):
    """Build right-handed orthonormal frame (u=+X-ish, v=+Z-ish, n=outward normal)."""
    n = Vector(normal).normalized()
    up = Vector((0.0, 0.0, 1.0))
    if abs(n.dot(up)) > 0.98:
        up = Vector((0.0, 1.0, 0.0))
    u = up.cross(n).normalized()
    if u.x < 0:
        u = -u
    v = n.cross(u).normalized()
    if v.z < 0:
        v = -v
    return u, v, n


def sample_surface(bvh, origin, ray_dir):
    hit, norm, _, _ = bvh.ray_cast(Vector(origin), Vector(ray_dir).normalized())
    if hit is None:
        return Vector(origin), -Vector(ray_dir).normalized()
    return hit, norm.normalized()


def ellipse_2d(rx, rz, segs=48, rot_deg=0.0):
    rad = math.radians(rot_deg)
    ca, sa = math.cos(rad), math.sin(rad)
    pts = []
    for i in range(segs):
        a = 2.0 * math.pi * i / segs
        px, py = rx * math.cos(a), rz * math.sin(a)
        pts.append((px * ca - py * sa, px * sa + py * ca))
    return pts


def teardrop_2d(half_w, half_h, segs=48, top_fullness=0.35):
    pts = []
    for i in range(segs):
        a = 2.0 * math.pi * i / segs
        s, c = math.sin(a), math.cos(a)
        w_mod = (1.0 - top_fullness * 0.8) + top_fullness * ((s + 1.0) * 0.5)
        pts.append((half_w * c * w_mod, half_h * s))
    return pts


def rounded_tri_2d(p0, p1, p2, corner_r=0.7, segs_per_corner=8):
    tri = [Vector(p0), Vector(p1), Vector(p2)]
    if (tri[1] - tri[0]).cross(tri[2] - tri[0]) < 0:
        tri = [tri[0], tri[2], tri[1]]
    pts = []
    for k in range(3):
        p_prev, p_curr, p_next = tri[(k - 1) % 3], tri[k], tri[(k + 1) % 3]
        d1 = (p_prev - p_curr).normalized()
        d2 = (p_next - p_curr).normalized()
        ang = math.acos(max(-1.0, min(1.0, d1.dot(d2))))
        dist = min(
            corner_r / max(0.2, math.tan(ang * 0.5)),
            (p_prev - p_curr).length * 0.35,
            (p_next - p_curr).length * 0.35,
        )
        q1, q2 = p_curr + d1 * dist, p_curr + d2 * dist
        for s in range(segs_per_corner + 1):
            t = s / segs_per_corner
            pt = (1 - t) * (1 - t) * q1 + 2 * (1 - t) * t * p_curr + t * t * q2
            pts.append((pt.x, pt.y))
    return pts


def rounded_rect_2d(half_w, half_h, radius, segs=8):
    pts = []
    corners = [
        (half_w - radius,  half_h - radius, 0.0,           math.pi * 0.5),
        (-half_w + radius, half_h - radius, math.pi * 0.5, math.pi),
        (-half_w + radius, -half_h + radius, math.pi,      math.pi * 1.5),
        (half_w - radius,  -half_h + radius, math.pi * 1.5, math.pi * 2.0),
    ]
    for ccx, ccy, a0, a1 in corners:
        for i in range(segs + 1):
            ang = a0 + (a1 - a0) * (i / segs)
            pts.append((ccx + radius * math.cos(ang), ccy + radius * math.sin(ang)))
    return pts


def offset_polygon_2d(pts_2d, expand):
    """Outward miter-clamped 2D polygon offset for CCW point lists."""
    if abs(expand) < 1e-6:
        return list(pts_2d)
    n = len(pts_2d)
    out = []
    for i in range(n):
        p_prev = Vector(pts_2d[(i - 1) % n])
        p_curr = Vector(pts_2d[i])
        p_next = Vector(pts_2d[(i + 1) % n])
        e1 = (p_curr - p_prev).normalized()
        e2 = (p_next - p_curr).normalized()
        n1 = Vector((e1.y, -e1.x))
        n2 = Vector((e2.y, -e2.x))
        bis = (n1 + n2).normalized() if (n1 + n2).length > 1e-6 else n1
        cos_h = max(0.35, bis.dot(n1))
        pt = p_curr + bis * (expand / cos_h)
        out.append((pt.x, pt.y))
    return out


def build_prism(pts_2d, center, u_ax, v_ax, n_ax, d_in, d_out, expand=0.0):
    """Extrude a 2D CCW contour along n_ax from d_in to d_out with optional radial offset."""
    pts = offset_polygon_2d(pts_2d, expand)
    n = len(pts)
    bm = bmesh.new()
    v_in = [bm.verts.new(center + u_ax * px + v_ax * py + n_ax * d_in) for (px, py) in pts]
    v_out = [bm.verts.new(center + u_ax * px + v_ax * py + n_ax * d_out) for (px, py) in pts]
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((v_in[i], v_in[j], v_out[j], v_out[i]))
    bm.faces.new(list(reversed(v_in)))
    bm.faces.new(v_out)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def build_surface_insert(bm_master, pts_2d, center, u_ax, v_ax, n_ax, depth_in, depth_out=4.0, tol=0.18):
    """
    Create a surface-conformed, flat-backed printable plug AND its clearance socket cutter.
    Returns (bm_plug, bm_cutter).
    """
    bm_p = build_prism(pts_2d, center, u_ax, v_ax, n_ax, -depth_in, depth_out, expand=0.0)
    bm_plug = bool_op(bm_master, bm_p, 'INTERSECT')
    bm_p.free()
    bm_cutter = build_prism(pts_2d, center, u_ax, v_ax, n_ax, -(depth_in + 0.15), depth_out + 1.0, expand=tol)
    return bm_plug, bm_cutter


def build_slide_split_volume(x_min, x_max, z_top, mask_z_fn, y_front, y_back, y_ref, slide_dz_dy, steps=80, expand=0.0, y_surf_fn=None):
    """
    Build a smooth, undercut-free linearly extruded split volume for 2-half shell splitting.
    - mask_z_fn(abs_x): desired front-surface mask height Z at |x|.
    - slide_dz_dy: slope of the straight slide-on path (e.g., -0.24 slides on from back-top).
    - expand: +TOL (0.18 mm) for the female subtraction volume, 0.0 for the male cap intersection.
    """
    xs = [x_min + (x_max - x_min) * i / steps for i in range(steps + 1)]
    pts_xz = []
    for x in xs:
        ax = abs(x)
        y_surf = y_surf_fn(ax) if y_surf_fn else y_ref
        z_ref = mask_z_fn(ax) - slide_dz_dy * (y_surf - y_ref) - expand
        pts_xz.append((x, z_ref))
    pts_xz.append((x_max, z_top))
    pts_xz.append((x_min, z_top))

    bm = bmesh.new()
    dy_f = y_front - y_ref
    dy_b = y_back - y_ref
    vf = [bm.verts.new((px, y_front, pz + slide_dz_dy * dy_f)) for (px, pz) in pts_xz]
    vb = [bm.verts.new((px, y_back, pz + slide_dz_dy * dy_b)) for (px, pz) in pts_xz]
    n = len(pts_xz)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((vf[i], vf[j], vb[j], vb[i]))
    bm.faces.new(list(reversed(vf)))
    bm.faces.new(vb)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def add_alignment_pin(bm_male, bm_female, origin, axis_dir, radius=1.8, length=3.0, tol=0.18):
    """
    Add a cylindrical alignment pin to `bm_male` and a matching +tol socket to `bm_female`
    along `axis_dir` (e.g., the shell slide vector) for slip-free assembly.
    Returns (bm_male_new, bm_female_new).
    """
    u, v, n = make_tangent_frame(axis_dir)
    pin_pts = ellipse_2d(radius, radius, segs=32)
    bm_pin = build_prism(pin_pts, Vector(origin), u, v, n, -1.5, length, expand=0.0)
    bm_sock = build_prism(pin_pts, Vector(origin), u, v, n, -0.5, length + 0.3, expand=tol)
    m_new = bool_op(bm_male, bm_pin, 'UNION')
    f_new = bool_op(bm_female, bm_sock, 'DIFFERENCE')
    bm_pin.free()
    bm_sock.free()
    return m_new, f_new


# =============================================================================
# 5. VERIFICATION & AUTO-FLAT PRINT-BED STL EXPORT (WITH OPTIONAL CHAMFER)
# =============================================================================

def verify_bvh_zone(bm_new, bm_ref, zone_filter_fn):
    """
    Bidirectional BVH surface deviation check inside a specific mechanical/connector zone.
    Returns (max_err_new_to_ref, max_err_ref_to_new, n_new, n_ref).
    """
    bvh_new = BVHTree.FromBMesh(bm_new)
    bvh_ref = BVHTree.FromBMesh(bm_ref)
    pts_n = [v.co for v in bm_new.verts if zone_filter_fn(v.co)]
    pts_r = [v.co for v in bm_ref.verts if zone_filter_fn(v.co)]
    e_nr = max((bvh_ref.find_nearest(p)[3] for p in pts_n), default=0.0)
    e_rn = max((bvh_new.find_nearest(p)[3] for p in pts_r), default=0.0)
    return e_nr, e_rn, len(pts_n), len(pts_r)


def orient_largest_flat_to_z0(bm):
    """Rotate bmesh so its largest coplanar face group lies flat facing -Z (Z = 0 build plate)."""
    n_areas = defaultdict(float)
    n_vecs = {}
    for f in bm.faces:
        key = (round(f.normal.x, 2), round(f.normal.y, 2), round(f.normal.z, 2))
        n_areas[key] += f.calc_area()
        if key not in n_vecs:
            n_vecs[key] = f.normal.copy()
    best_key = max(n_areas.keys(), key=lambda k: n_areas[k])
    flat_n = n_vecs[best_key].normalized()
    q = flat_n.rotation_difference(Vector((0.0, 0.0, -1.0)))
    bmesh.ops.transform(bm, matrix=q.to_matrix().to_4x4(), verts=bm.verts)


def apply_bottom_elephant_foot_chamfer(bm, chamfer=0.20):
    """Apply a clean 45° bottom perimeter bevel on Z = 0 faces to prevent FDM elephant-foot jamming."""
    if chamfer <= 0.0:
        return
    min_z = min(v.co.z for v in bm.verts)
    bot_edges = [
        e for e in bm.edges
        if abs(e.verts[0].co.z - min_z) < 0.02
        and abs(e.verts[1].co.z - min_z) < 0.02
        and len(e.link_faces) == 2
        and abs(e.link_faces[0].normal.dot(e.link_faces[1].normal)) < 0.5
    ]
    if bot_edges:
        bmesh.ops.bevel(
            bm,
            geom=bot_edges,
            offset=chamfer,
            offset_type='OFFSET',
            segments=1,
            profile=0.5,
            affect='EDGES',
            clamp_overlap=True,
        )
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)


def export_flat_stl(
    obj,
    filepath,
    auto_orient_flat=False,
    apply_modifiers=False,
    bottom_chamfer=0.0,
):
    """
    Export a print-ready binary STL centered in XY with Z_min = 0.0.
    Never modifies the scene object's assembled transform.
    Returns (dims_xyz, non_manifold_count, size_kb).
    """
    bm = snapshot_evaluated_bmesh(obj) if apply_modifiers else bmesh.new()
    if not apply_modifiers:
        bm.from_mesh(obj.data)

    if auto_orient_flat:
        orient_largest_flat_to_z0(bm)

    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    zs = [v.co.z for v in bm.verts]
    bmesh.ops.transform(
        bm,
        matrix=Matrix.Translation((-(min(xs) + max(xs)) / 2.0, -(min(ys) + max(ys)) / 2.0, -min(zs))),
        verts=bm.verts,
    )

    if bottom_chamfer > 0.0:
        apply_bottom_elephant_foot_chamfer(bm, chamfer=bottom_chamfer)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    nm = count_non_manifold(bm)
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    zs = [v.co.z for v in bm.verts]
    dims = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))

    me_tmp = bpy.data.meshes.new("_nas_exp_tmp")
    bm.to_mesh(me_tmp)
    bm.free()
    ob_tmp = bpy.data.objects.new("_nas_exp_tmp", me_tmp)
    bpy.context.scene.collection.objects.link(ob_tmp)

    bpy.ops.object.select_all(action='DESELECT')
    ob_tmp.select_set(True)
    bpy.context.view_layer.objects.active = ob_tmp
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    bpy.ops.wm.stl_export(
        filepath=filepath,
        export_selected_objects=True,
        apply_modifiers=False,
        global_scale=1.0,
    )

    bpy.data.objects.remove(ob_tmp, do_unlink=True)
    if me_tmp.users == 0:
        bpy.data.meshes.remove(me_tmp)

    return dims, nm, os.path.getsize(filepath) / 1024.0

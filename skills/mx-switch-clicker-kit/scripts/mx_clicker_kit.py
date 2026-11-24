"""
Cherry MX Switch Clicker Holder Kit — Reusable Blender Python CAD Library
=========================================================================
Import inside Blender MCP `execute_blender_code`:

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path.home() / ".gemini/config/skills/mx-switch-clicker-kit/scripts"))
    import mx_clicker_kit as mxk

All geometry operates in 1 Blender Unit = 1 mm (standard 3D-print STL scale).
Compatible with Cherry MX, Gateron, Kailh, and Outemu standard MX-stem switches.
"""

import math
import os
from dataclasses import dataclass
import bpy
import bmesh
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree


# =============================================================================
# 1. VERIFIED CHERRY MX MECHANICAL SPECIFICATIONS (mm)
# =============================================================================

@dataclass
class MXSpec:
    # Base (Lower) — Square Switch Housing
    switch_cutout: float = 14.00      # Standard Cherry MX plate cutout (14.0 x 14.0 mm)
    housing_tol: float = 0.00         # Extra clearance per side (+0.05..0.10 if printer runs tight)
    socket_wall: float = 1.50         # Wall thickness around cutout -> 17.0 x 17.0 mm outer frame
    socket_outer_r: float = 1.00      # Outer corner fillet of square housing frame
    drop_in_height: float = 8.30      # Height of drop-in cup walls above floor (Z = 1.2..9.5 mm)
    snap_plate_thk: float = 1.50      # Standard MX clip-in plate lip thickness
    snap_relief_w: float = 15.60      # Lower cavity width below snap plate for clip tabs & pins

    # Topper (Upper) — Recess Pocket + Cross ('+') Stem
    recess_size: float = 17.60        # Outer switch housing clearance pocket (0.30 mm/side over 17.0)
    recess_corner_r: float = 2.50     # Corner radius of topper recess pocket
    recess_depth: float = 5.00        # Depth of topper recess pocket (Z = 0..5.0 mm)
    stem_post_dia: float = 5.60       # Cylindrical MX stem sleeve outer diameter (R = 2.80 mm)
    cross_arm_len: float = 4.20       # '+' cross slot total arm length (±2.10 mm)
    cross_arm_w: float = 1.35         # '+' cross slot arm width (1.30 tight / 1.35 std / 1.42 loose)
    cross_depth: float = 4.60         # '+' cross slot depth (leaves 0.40 mm roof below 5.0 recess)

    # Auto-Skirt (when topper neck/bottom is narrower than recess + walls)
    skirt_size: float = 20.80         # Uniform 1.60 mm wall around 17.60 mm recess
    skirt_corner_r: float = 4.10      # Concentric outer fillet (2.50 + 1.60 = 4.10 mm)
    skirt_height: float = 7.20        # Embeds cleanly upward into narrow topper body

    # Travel stroke
    click_stroke: float = 4.00        # Full Cherry MX actuation + bottom-out travel


DEFAULT_MX = MXSpec()


# =============================================================================
# 2. SCENE, COLLECTION & GEOMETRY PRIMITIVE HELPERS
# =============================================================================

def get_or_create_collection(name, parent=None):
    col = bpy.data.collections.get(name)
    if not col:
        col = bpy.data.collections.new(name)
        if parent:
            parent.children.link(col)
        else:
            bpy.context.scene.collection.children.link(col)
    return col


def _get_components_col():
    proj = get_or_create_collection("COL_Project")
    return get_or_create_collection("COL_Components", proj)


def _get_geo_col():
    proj = get_or_create_collection("COL_Project")
    return get_or_create_collection("COL_Geo", proj)


def _remove_if_exists(name):
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)


def rounded_rect_2d(half_w, half_h, radius, segs=8):
    """CCW 2D rounded rectangle vertices."""
    r = min(radius, half_w - 1e-4, half_h - 1e-4)
    if r <= 1e-4:
        return [(half_w, half_h), (-half_w, half_h), (-half_w, -half_h), (half_w, -half_h)]
    pts = []
    corners = [
        (half_w - r,  half_h - r, 0.0,           math.pi * 0.5),
        (-half_w + r, half_h - r, math.pi * 0.5, math.pi),
        (-half_w + r, -half_h + r, math.pi,      math.pi * 1.5),
        (half_w - r,  -half_h + r, math.pi * 1.5, math.pi * 2.0),
    ]
    for ccx, ccy, a0, a1 in corners:
        for i in range(segs + 1):
            ang = a0 + (a1 - a0) * (i / segs)
            pts.append((ccx + r * math.cos(ang), ccy + r * math.sin(ang)))
    return pts


def cross_2d(arm_len, arm_w):
    """12-vertex CCW '+' cross polygon centered at origin."""
    a = arm_len * 0.5
    w = arm_w * 0.5
    return [
        ( w,  w), ( w,  a), (-w,  a),
        (-w,  w), (-a,  w), (-a, -w),
        (-w, -w), (-w, -a), ( w, -a),
        ( w, -w), ( a, -w), ( a,  w),
    ]


def _make_extruded_obj(name, pts_2d, z0, z1, loc, rot_z_rad, col, parent=None, hide=True):
    _remove_if_exists(name)
    bm = bmesh.new()
    vb = [bm.verts.new((x, y, z0)) for (x, y) in pts_2d]
    vt = [bm.verts.new((x, y, z1)) for (x, y) in pts_2d]
    n = len(pts_2d)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((vb[i], vb[j], vt[j], vt[i]))
    bm.faces.new(list(reversed(vb)))
    bm.faces.new(vt)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name + "_Mesh")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = Vector(loc)
    ob.rotation_euler = Euler((0.0, 0.0, rot_z_rad))
    col.objects.link(ob)
    if parent:
        ob.parent = parent
    ob.hide_viewport = hide
    ob.hide_render = hide
    return ob


def _make_hollow_frame_obj(name, outer_half, outer_r, inner_half, z0, z1, loc, rot_z_rad, col, parent=None, hide=True, segs=6):
    """Build a watertight rounded-outer / sharp-square-inner housing cup wall."""
    _remove_if_exists(name)
    outer_pts = rounded_rect_2d(outer_half, outer_half, outer_r, segs=segs)
    bm = bmesh.new()
    so_b = [bm.verts.new((x, y, z0)) for (x, y) in outer_pts]
    so_t = [bm.verts.new((x, y, z1)) for (x, y) in outer_pts]
    si_coords = [(inner_half, inner_half), (-inner_half, inner_half), (-inner_half, -inner_half), (inner_half, -inner_half)]
    si_b = [bm.verts.new((x, y, z0)) for (x, y) in si_coords]
    si_t = [bm.verts.new((x, y, z1)) for (x, y) in si_coords]

    n_so = len(outer_pts)
    for i in range(n_so):
        j = (i + 1) % n_so
        bm.faces.new((so_b[i], so_b[j], so_t[j], so_t[i]))
    for k in range(4):
        kn = (k + 1) % 4
        bm.faces.new((si_t[k], si_t[kn], si_b[kn], si_b[k]))

    pts_per_corner = segs + 1
    for k in range(4):
        kn = (k + 1) % 4
        base = k * pts_per_corner
        for i in range(segs):
            bm.faces.new((so_t[base + i], so_t[base + i + 1], si_t[k]))
            bm.faces.new((so_b[base + i + 1], so_b[base + i], si_b[k]))
        bm.faces.new((so_t[base + segs], so_t[kn * pts_per_corner], si_t[kn], si_t[k]))
        bm.faces.new((so_b[kn * pts_per_corner], so_b[base + segs], si_b[k], si_b[kn]))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name + "_Mesh")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = Vector(loc)
    ob.rotation_euler = Euler((0.0, 0.0, rot_z_rad))
    col.objects.link(ob)
    if parent:
        ob.parent = parent
    ob.hide_viewport = hide
    ob.hide_render = hide
    return ob


def _add_exact_boolean(target_obj, mod_name, op, operand_obj, index=None):
    old = target_obj.modifiers.get(mod_name)
    if old:
        target_obj.modifiers.remove(old)
    mod = target_obj.modifiers.new(mod_name, 'BOOLEAN')
    mod.operation = op
    mod.solver = 'EXACT'
    mod.object = operand_obj
    if index is not None:
        bpy.context.view_layer.objects.active = target_obj
        bpy.ops.object.modifier_move_to_index(modifier=mod_name, index=index)
    return mod


def _eval_bmesh(obj, world=False):
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    bm = bmesh.new()
    bm.from_mesh(ev.to_mesh())
    if world:
        bmesh.ops.transform(bm, matrix=ev.matrix_world, verts=bm.verts)
    ev.to_mesh_clear()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


# =============================================================================
# 3. BASE SIDE — LOWER SQUARE MX SWITCH HOUSING (DROP-IN & SNAP-IN MODES)
# =============================================================================

def attach_mx_base_socket(
    base_obj,
    xy=(0.0, 0.0),
    floor_z=1.20,
    rot_deg=0.0,
    mode="drop_in",
    spec: MXSpec = DEFAULT_MX,
    pushout_hole_r=0.0,
    top_z=None,
):
    """
    Attach a Cherry MX square switch socket to ANY base object via non-destructive Exact Booleans.

    Modes:
    - "drop_in" (default): Unions a 17.0x17.0 mm (R=1.0), 8.3 mm tall square socket cup with a
      14.0x14.0 mm inner opening seated cleanly on `floor_z` (hides switch pins, zero supports).
      Set `pushout_hole_r=4.5` to punch a bottom push-out finger/tool hole if desired.
    - "snap_in": Carves a true 1.5 mm thick 14.0x14.0 mm clip-in plate at `top_z` (default: base max Z)
      with a 15.6x15.6 mm lower cavity extending down through the bottom (or to `floor_z`) for switch
      clip tabs & metal pin clearance.
    """
    col_parts = _get_components_col()
    rot_rad = math.radians(rot_deg)
    loc = Vector((xy[0], xy[1], 0.0))
    prefix = base_obj.name
    cut_half = (spec.switch_cutout + 2.0 * spec.housing_tol) * 0.5
    outer_half = cut_half + spec.socket_wall

    if mode == "drop_in":
        z_bot = max(0.0, floor_z - 0.6)  # embed 0.6 mm cleanly into floor for watertight Boolean UNION
        z_top = top_z if top_z is not None else (floor_z + spec.drop_in_height)
        ob_sock = _make_hollow_frame_obj(
            f"ADD_{prefix}_MX_Socket",
            outer_half=outer_half,
            outer_r=spec.socket_outer_r,
            inner_half=cut_half,
            z0=z_bot,
            z1=z_top,
            loc=loc,
            rot_z_rad=rot_rad,
            col=col_parts,
            parent=base_obj,
            hide=True,
        )
        _add_exact_boolean(base_obj, "BOOL_MX_Base_Socket", 'UNION', ob_sock)

        # Ensure the inner 14.0x14.0 opening is completely clear down to floor_z (in case base was solid!)
        inner_pts = rounded_rect_2d(cut_half, cut_half, 0.0, segs=1)
        ob_clr = _make_extruded_obj(
            f"CUT_{prefix}_MX_Clear",
            inner_pts,
            z0=floor_z,
            z1=z_top + 1.0,
            loc=loc,
            rot_z_rad=rot_rad,
            col=col_parts,
            parent=base_obj,
            hide=True,
        )
        _add_exact_boolean(base_obj, "BOOL_MX_Base_Clear", 'DIFFERENCE', ob_clr)

        if pushout_hole_r > 0.5:
            hole_pts = [
                (pushout_hole_r * math.cos(2 * math.pi * i / 48), pushout_hole_r * math.sin(2 * math.pi * i / 48))
                for i in range(48)
            ]
            ob_hole = _make_extruded_obj(
                f"CUT_{prefix}_MX_Pushout",
                hole_pts,
                z0=-0.5,
                z1=floor_z + 0.5,
                loc=loc,
                rot_z_rad=rot_rad,
                col=col_parts,
                parent=base_obj,
                hide=True,
            )
            _add_exact_boolean(base_obj, "BOOL_MX_Pushout_Hole", 'DIFFERENCE', ob_hole)

    elif mode == "snap_in":
        base_max_z = max(v.co.z for v in base_obj.data.vertices)
        z_plate_top = top_z if top_z is not None else base_max_z
        z_plate_bot = z_plate_top - spec.snap_plate_thk

        # 1. Top 14.0x14.0 square clip cutout through the 1.5 mm top plate
        inner_pts = rounded_rect_2d(cut_half, cut_half, 0.0, segs=1)
        ob_cut = _make_extruded_obj(
            f"CUT_{prefix}_MX_SnapCut",
            inner_pts,
            z0=z_plate_bot - 0.5,
            z1=z_plate_top + 1.0,
            loc=loc,
            rot_z_rad=rot_rad,
            col=col_parts,
            parent=base_obj,
            hide=True,
        )
        _add_exact_boolean(base_obj, "BOOL_MX_Snap_Cutout", 'DIFFERENCE', ob_cut)

        # 2. Lower 15.6x15.6 relief cavity for switch clip tabs & pins (open bottom or down to floor_z)
        relief_half = spec.snap_relief_w * 0.5
        relief_pts = rounded_rect_2d(relief_half, relief_half, 1.0, segs=6)
        z_cav_bot = -0.5 if floor_z <= 0.0 else floor_z
        ob_rel = _make_extruded_obj(
            f"CUT_{prefix}_MX_SnapRelief",
            relief_pts,
            z0=z_cav_bot,
            z1=z_plate_bot,
            loc=loc,
            rot_z_rad=rot_rad,
            col=col_parts,
            parent=base_obj,
            hide=True,
        )
        _add_exact_boolean(base_obj, "BOOL_MX_Snap_Relief", 'DIFFERENCE', ob_rel)
    else:
        raise ValueError(f"Unknown mode '{mode}'. Use 'drop_in' or 'snap_in'.")

    bpy.context.view_layer.update()


# =============================================================================
# 4. TOPPER SIDE — UPPER RECESS POCKET + CROSS ('+') STEM CONNECTOR
# =============================================================================

def _footprint_needs_skirt(topper_obj, xy, rot_rad, spec: MXSpec):
    """Return True if the topper mesh at Z=0..5 mm doesn't fully enclose the 20.8x20.8 skirt footprint."""
    ca, sa = math.cos(-rot_rad), math.sin(-rot_rad)
    check_pts = rounded_rect_2d(spec.recess_size * 0.5 + 1.2, spec.recess_size * 0.5 + 1.2, spec.recess_corner_r + 1.2, segs=4)
    # Check bounding extents in rotated MX frame for vertices near Z = 0..2.0 mm
    near_bot = [v.co for v in topper_obj.data.vertices if v.co.z <= 2.5]
    if not near_bot:
        return True
    us = [(p.x - xy[0]) * ca - (p.y - xy[1]) * sa for p in near_bot]
    vs = [(p.x - xy[0]) * sa + (p.y - xy[1]) * ca for p in near_bot]
    req = spec.skirt_size * 0.5 - 0.4
    return (min(us) > -req) or (max(us) < req) or (min(vs) > -req) or (max(vs) < req)


def attach_mx_topper_connector(
    topper_obj,
    xy=(0.0, 0.0),
    rot_deg=0.0,
    spec: MXSpec = DEFAULT_MX,
    auto_skirt=True,
    force_skirt=False,
    slice_flat_z=None,
    skirt_material=None,
):
    """
    Carve the exact Cherry MX topper connector into ANY watertight 3D topper object:
      - Optional flat bottom slice at `slice_flat_z` (shifts sliced bottom to local Z = 0.0).
      - Auto-skirt (20.8x20.8 R=4.1 mm) if the topper's base is narrower than the recess + walls.
      - Outer clearance recess: 17.6x17.6 mm (R=2.5 mm), Z = 0.0..5.0 mm.
      - Central stem post: Ø 5.6 mm cylinder, Z = 0.0..5.0 mm.
      - Cross '+' slot: 4.20 x 1.35 mm, Z = 0.0..4.6 mm.
    """
    col_parts = _get_components_col()
    rot_rad = math.radians(rot_deg)
    loc = Vector((xy[0], xy[1], 0.0))
    prefix = topper_obj.name

    # Optional clean flat bottom slice
    if slice_flat_z is not None:
        bm = bmesh.new()
        bm.from_mesh(topper_obj.data)
        bmesh.ops.bisect_plane(
            bm,
            geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
            plane_co=(0.0, 0.0, slice_flat_z),
            plane_no=(0.0, 0.0, 1.0),
            clear_inner=True,
            clear_outer=False,
        )
        bmesh.ops.transform(bm, matrix=Matrix.Translation((0.0, 0.0, -slice_flat_z)), verts=bm.verts)
        open_edges = [e for e in bm.edges if e.is_boundary]
        if open_edges:
            bmesh.ops.contextual_create(bm, geom=open_edges)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(topper_obj.data)
        bm.free()
        topper_obj.data.update()

    # 1. Optional Auto-Skirt
    need_skirt = force_skirt or (auto_skirt and _footprint_needs_skirt(topper_obj, xy, rot_rad, spec))
    if need_skirt:
        skirt_pts = rounded_rect_2d(spec.skirt_size * 0.5, spec.skirt_size * 0.5, spec.skirt_corner_r, segs=8)
        ob_skirt = _make_extruded_obj(
            f"ADD_{prefix}_MX_Skirt",
            skirt_pts,
            z0=0.0,
            z1=spec.skirt_height,
            loc=loc,
            rot_z_rad=rot_rad,
            col=col_parts,
            parent=topper_obj,
            hide=True,
        )
        if skirt_material:
            ob_skirt.data.materials.append(skirt_material)
        _add_exact_boolean(topper_obj, "BOOL_MX_Add_Skirt", 'UNION', ob_skirt)

    # 2. Outer Switch Housing Clearance Recess (17.6x17.6 R=2.5, Z=-0.5..5.0)
    rec_pts = rounded_rect_2d(spec.recess_size * 0.5, spec.recess_size * 0.5, spec.recess_corner_r, segs=8)
    ob_rec = _make_extruded_obj(
        f"CUT_{prefix}_MX_Recess",
        rec_pts,
        z0=-0.5,
        z1=spec.recess_depth,
        loc=loc,
        rot_z_rad=rot_rad,
        col=col_parts,
        parent=topper_obj,
        hide=True,
    )

    # 3. Central Cylindrical Stem Post (Ø 5.6 mm, Z=0.0..5.6 — embedded 0.6 mm into roof)
    post_name = f"ADD_{prefix}_MX_StemPost"
    _remove_if_exists(post_name)
    bm_p = bmesh.new()
    post_h = spec.recess_depth + 0.6
    bmesh.ops.create_cone(
        bm_p,
        cap_ends=True,
        cap_tris=False,
        segments=64,
        radius1=spec.stem_post_dia * 0.5,
        radius2=spec.stem_post_dia * 0.5,
        depth=post_h,
        matrix=Matrix.Translation((0.0, 0.0, post_h * 0.5)),
    )
    bmesh.ops.recalc_face_normals(bm_p, faces=bm_p.faces)
    me_p = bpy.data.meshes.new(post_name + "_Mesh")
    bm_p.to_mesh(me_p)
    bm_p.free()
    ob_post = bpy.data.objects.new(post_name, me_p)
    ob_post.location = loc
    ob_post.rotation_euler = Euler((0.0, 0.0, rot_rad))
    col_parts.objects.link(ob_post)
    ob_post.parent = topper_obj
    ob_post.hide_viewport = True
    ob_post.hide_render = True

    # 4. Cross ('+') Stem Slot Cutter (4.20 x 1.35 mm, Z=-0.5..4.6)
    x_pts = cross_2d(spec.cross_arm_len, spec.cross_arm_w)
    ob_cross = _make_extruded_obj(
        f"CUT_{prefix}_MX_Cross",
        x_pts,
        z0=-0.5,
        z1=spec.cross_depth,
        loc=loc,
        rot_z_rad=rot_rad,
        col=col_parts,
        parent=topper_obj,
        hide=True,
    )

    if skirt_material:
        for o in (ob_rec, ob_post, ob_cross):
            o.data.materials.append(skirt_material)

    _add_exact_boolean(topper_obj, "BOOL_MX_Cut_Recess", 'DIFFERENCE', ob_rec)
    _add_exact_boolean(topper_obj, "BOOL_MX_Add_StemPost", 'UNION', ob_post)
    _add_exact_boolean(topper_obj, "BOOL_MX_Cut_Cross", 'DIFFERENCE', ob_cross)

    bpy.context.view_layer.update()
    return need_skirt


# =============================================================================
# 5. PARAMETRIC BASE PRESETS & KEYCHAIN LOOP
# =============================================================================

def create_square_base(
    name="SM_Clicker_Base_Square",
    size=24.0,
    height=9.5,
    corner_r=3.0,
    floor_z=1.2,
    mode="drop_in",
    rot_deg=0.0,
    spec: MXSpec = DEFAULT_MX,
    pushout_hole_r=0.0,
):
    """Create a sleek rounded-square handheld clicker base with built-in MX socket."""
    col_geo = _get_geo_col()
    pts = rounded_rect_2d(size * 0.5, size * 0.5, corner_r, segs=10)
    ob = _make_extruded_obj(name, pts, 0.0, height, (0, 0, 0), 0.0, col_geo, hide=False)
    attach_mx_base_socket(
        ob, xy=(0, 0), floor_z=floor_z, rot_deg=rot_deg, mode=mode, spec=spec,
        pushout_hole_r=pushout_hole_r, top_z=height
    )
    return ob


def create_round_puck_base(
    name="SM_Clicker_Base_Round",
    diameter=28.0,
    height=9.5,
    floor_z=1.2,
    mode="drop_in",
    rot_deg=0.0,
    spec: MXSpec = DEFAULT_MX,
    pushout_hole_r=0.0,
    segs=64,
):
    """Create a sleek cylindrical coin/puck clicker base with built-in MX socket."""
    col_geo = _get_geo_col()
    r = diameter * 0.5
    pts = [(r * math.cos(2 * math.pi * i / segs), r * math.sin(2 * math.pi * i / segs)) for i in range(segs)]
    ob = _make_extruded_obj(name, pts, 0.0, height, (0, 0, 0), 0.0, col_geo, hide=False)
    attach_mx_base_socket(
        ob, xy=(0, 0), floor_z=floor_z, rot_deg=rot_deg, mode=mode, spec=spec,
        pushout_hole_r=pushout_hole_r, top_z=height
    )
    return ob


def create_box_base(
    name="SM_Clicker_Base_Box",
    outer_w=39.316,
    height=23.3427,
    wall=1.6,
    floor_z=1.2,
    outer_r=2.2,
    inner_r=1.0,
    flaps=True,
    socket_xy=(0.0, 0.0),
    socket_rot_deg=45.0,
    mode="drop_in",
    spec: MXSpec = DEFAULT_MX,
    pushout_hole_r=0.0,
):
    """Create a MakerWorld-style folded cardboard box clicker base (with optional 4 tilted flaps)."""
    col_geo = _get_geo_col()
    col_parts = _get_components_col()
    _remove_if_exists(name)

    half_o = outer_w * 0.5
    half_i = half_o - wall
    outer_pts = rounded_rect_2d(half_o, half_o, outer_r, segs=12)
    inner_pts = rounded_rect_2d(half_i, half_i, inner_r, segs=12)
    n = len(outer_pts)

    bm = bmesh.new()
    vob = [bm.verts.new((x, y, 0.0)) for (x, y) in outer_pts]
    vot = [bm.verts.new((x, y, height)) for (x, y) in outer_pts]
    vit = [bm.verts.new((x, y, height)) for (x, y) in inner_pts]
    vif = [bm.verts.new((x, y, floor_z)) for (x, y) in inner_pts]

    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((vob[i], vob[j], vot[j], vot[i]))
        bm.faces.new((vot[i], vot[j], vit[j], vit[i]))
        bm.faces.new((vit[i], vit[j], vif[j], vif[i]))
    bm.faces.new(list(reversed(vob)))
    bm.faces.new(vif)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    me = bpy.data.meshes.new(name + "_Mesh")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    col_geo.objects.link(ob)

    if flaps:
        flap_name = f"ADD_{name}_Flaps"
        _remove_if_exists(flap_name)
        ang = math.radians(14.0)
        ca, sa = math.cos(ang), math.sin(ang)
        flap_len, flap_thk = 9.0, 1.2
        p_ot = Vector((half_o + 0.665, 0.0, height - 0.01))
        p_ob = p_ot + Vector((flap_len * sa, 0.0, -flap_len * ca))
        p_ib = p_ob + Vector((-flap_thk * ca, 0.0, -flap_thk * sa))
        p_it = p_ot + Vector((-flap_thk * ca, 0.0, -flap_thk * sa))
        y_top = half_o - 1.5
        y_bot = y_top - 1.25

        bm_f = bmesh.new()
        for k in range(4):
            rot = Matrix.Rotation(k * math.pi * 0.5, 4, 'Z')
            pts = [
                Vector((p_ot.x, -y_top, p_ot.z)), Vector((p_ot.x,  y_top, p_ot.z)),
                Vector((p_ob.x,  y_bot, p_ob.z)), Vector((p_ob.x, -y_bot, p_ob.z)),
                Vector((p_it.x, -y_top, p_it.z)), Vector((p_it.x,  y_top, p_it.z)),
                Vector((p_ib.x,  y_bot, p_ib.z)), Vector((p_ib.x, -y_bot, p_ib.z)),
            ]
            vs = [bm_f.verts.new(rot @ p) for p in pts]
            bm_f.faces.new((vs[0], vs[1], vs[2], vs[3]))
            bm_f.faces.new((vs[5], vs[4], vs[7], vs[6]))
            bm_f.faces.new((vs[4], vs[5], vs[1], vs[0]))
            bm_f.faces.new((vs[3], vs[2], vs[6], vs[7]))
            bm_f.faces.new((vs[1], vs[5], vs[6], vs[2]))
            bm_f.faces.new((vs[4], vs[0], vs[3], vs[7]))
        bmesh.ops.recalc_face_normals(bm_f, faces=bm_f.faces)
        me_f = bpy.data.meshes.new(flap_name + "_Mesh")
        bm_f.to_mesh(me_f)
        bm_f.free()
        ob_flaps = bpy.data.objects.new(flap_name, me_f)
        col_parts.objects.link(ob_flaps)
        ob_flaps.parent = ob
        ob_flaps.hide_viewport = True
        ob_flaps.hide_render = True
        _add_exact_boolean(ob, "BOOL_Box_Flaps", 'UNION', ob_flaps)

    attach_mx_base_socket(
        ob, xy=socket_xy, floor_z=floor_z, rot_deg=socket_rot_deg, mode=mode,
        spec=spec, pushout_hole_r=pushout_hole_r, top_z=(floor_z + spec.drop_in_height)
    )
    return ob


def attach_keychain_loop(
    base_obj,
    side="+Y",
    outer_r=4.2,
    hole_r=2.2,
    thickness=3.6,
    z_bot=0.0,
    overlap=1.8,
):
    """
    Attach a sturdy, support-free horizontal keychain eyelet (Z = z_bot..z_bot+thickness)
    to any side ("+X", "-X", "+Y", "-Y", or corner "+X+Y", etc.) of `base_obj`.
    """
    col_parts = _get_components_col()
    bm_eval = _eval_bmesh(base_obj, world=False)
    xs = [v.co.x for v in bm_eval.verts]
    ys = [v.co.y for v in bm_eval.verts]
    bm_eval.free()

    side_dirs = {
        "+X": (Vector((1, 0, 0)), max(xs)),
        "-X": (Vector((-1, 0, 0)), abs(min(xs))),
        "+Y": (Vector((0, 1, 0)), max(ys)),
        "-Y": (Vector((0, -1, 0)), abs(min(ys))),
        "+X+Y": (Vector((1, 1, 0)).normalized(), math.hypot(max(xs), max(ys)) * 0.85),
    }
    direction, edge_dist = side_dirs.get(side, side_dirs["+Y"])
    # Center of loop sits outside the edge so the hole is clear while the ring embeds by `overlap`
    loop_center = direction * (edge_dist + outer_r - overlap)
    loop_center.z = 0.0

    segs = 48
    loop_name = f"ADD_{base_obj.name}_KeychainLoop"
    _remove_if_exists(loop_name)
    bm = bmesh.new()
    ob_pts = [(outer_r * math.cos(2 * math.pi * i / segs), outer_r * math.sin(2 * math.pi * i / segs)) for i in range(segs)]
    in_pts = [(hole_r * math.cos(2 * math.pi * i / segs), hole_r * math.sin(2 * math.pi * i / segs)) for i in range(segs)]
    vob = [bm.verts.new((x, y, z_bot)) for (x, y) in ob_pts]
    vot = [bm.verts.new((x, y, z_bot + thickness)) for (x, y) in ob_pts]
    vib = [bm.verts.new((x, y, z_bot)) for (x, y) in in_pts]
    vit = [bm.verts.new((x, y, z_bot + thickness)) for (x, y) in in_pts]
    for i in range(segs):
        j = (i + 1) % segs
        bm.faces.new((vob[i], vob[j], vot[j], vot[i]))
        bm.faces.new((vit[i], vit[j], vib[j], vib[i]))
        bm.faces.new((vot[i], vot[j], vit[j], vit[i]))
        bm.faces.new((vib[i], vib[j], vob[j], vob[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    me = bpy.data.meshes.new(loop_name + "_Mesh")
    bm.to_mesh(me)
    bm.free()
    ob_loop = bpy.data.objects.new(loop_name, me)
    ob_loop.location = loop_center
    col_parts.objects.link(ob_loop)
    ob_loop.parent = base_obj
    ob_loop.hide_viewport = True
    ob_loop.hide_render = True

    _add_exact_boolean(base_obj, "BOOL_Keychain_Loop", 'UNION', ob_loop)
    bpy.context.view_layer.update()
    return ob_loop


# =============================================================================
# 6. VERIFICATION (MANIFOLD + 4 MM TRAVEL COLLISION) & FLAT STL EXPORT
# =============================================================================

def verify_mx_fit(base_obj, topper_obj, xy=(0.0, 0.0), rot_deg=0.0, spec: MXSpec = DEFAULT_MX):
    """Verify manifoldness and measure exact evaluated MX connector geometry on both parts."""
    bm_b = _eval_bmesh(base_obj, world=False)
    bm_t = _eval_bmesh(topper_obj, world=False)
    nm_b = sum(1 for e in bm_b.edges if not e.is_manifold)
    nm_t = sum(1 for e in bm_t.edges if not e.is_manifold)

    rot_rad = -math.radians(rot_deg)
    ca, sa = math.cos(rot_rad), math.sin(rot_rad)
    to_loc = lambda p: ((p.x - xy[0]) * ca - (p.y - xy[1]) * sa, (p.x - xy[0]) * sa + (p.y - xy[1]) * ca)

    # Measure topper cross ceiling (Z = spec.cross_depth) & recess ceiling (Z = spec.recess_depth)
    p_cross = [to_loc(v.co) for f in bm_t.faces if abs(f.normal.z) > 0.99 and abs(f.calc_center_median().z - spec.cross_depth) < 0.05 for v in f.verts]
    p_rec = [to_loc(v.co) for f in bm_t.faces if abs(f.normal.z) > 0.99 and abs(f.calc_center_median().z - spec.recess_depth) < 0.05 for v in f.verts]

    report = {
        "base_non_manifold": nm_b,
        "topper_non_manifold": nm_t,
        "cross_detected": len(p_cross) >= 12,
        "recess_detected": len(p_rec) >= 16,
    }
    if p_cross:
        report["cross_len_u"] = round(max(u for u, v in p_cross) - min(u for u, v in p_cross), 4)
        report["cross_len_v"] = round(max(v for u, v in p_cross) - min(v for u, v in p_cross), 4)
    if p_rec:
        wall = [(u, v) for u, v in p_rec if math.hypot(u, v) > 6.0]
        if wall:
            report["recess_w"] = round(max(u for u, v in wall) - min(u for u, v in wall), 4)
            report["recess_h"] = round(max(v for u, v in wall) - min(v for u, v in wall), 4)

    bm_b.free()
    bm_t.free()
    return report


def verify_travel_clearance(base_obj, topper_obj, rest_z=14.0, stroke=4.0, steps=(0.0, 2.0, 4.0)):
    """
    Simulate pressing `topper_obj` straight down by `stroke` mm inside `base_obj`.
    Returns dict mapping depression_mm -> overlapping_triangle_pairs (0 = completely collision-free!).
    """
    bm_b = _eval_bmesh(base_obj, world=True)
    bvh_b = BVHTree.FromBMesh(bm_b)
    bm_t_local = _eval_bmesh(topper_obj, world=False)

    results = {}
    for dz in steps:
        bm_t = bm_t_local.copy()
        test_mat = Matrix.Translation((topper_obj.location.x, topper_obj.location.y, rest_z - dz))
        bmesh.ops.transform(bm_t, matrix=test_mat, verts=bm_t.verts)
        bvh_t = BVHTree.FromBMesh(bm_t)
        overlaps = bvh_b.overlap(bvh_t)
        results[dz] = len(overlaps)
        bm_t.free()

    bm_b.free()
    bm_t_local.free()
    return results


def export_clicker_stls(base_obj, topper_obj, out_dir, prefix="clicker"):
    """Export both Base and Topper flat on Z = 0 (1 BU = 1 mm, modifiers applied) without moving scene objects."""
    os.makedirs(out_dir, exist_ok=True)
    outputs = {}
    for tag, ob in [("base", base_obj), ("topper", topper_obj)]:
        bm = _eval_bmesh(ob, world=False)
        xs = [v.co.x for v in bm.verts]
        ys = [v.co.y for v in bm.verts]
        zs = [v.co.z for v in bm.verts]
        bmesh.ops.transform(
            bm,
            matrix=Matrix.Translation((-(min(xs) + max(xs)) / 2.0, -(min(ys) + max(ys)) / 2.0, -min(zs))),
            verts=bm.verts,
        )
        nm = sum(1 for e in bm.edges if not e.is_manifold)
        me_tmp = bpy.data.meshes.new("_mxk_exp")
        bm.to_mesh(me_tmp)
        bm.free()
        ob_tmp = bpy.data.objects.new("_mxk_exp", me_tmp)
        bpy.context.scene.collection.objects.link(ob_tmp)

        bpy.ops.object.select_all(action='DESELECT')
        ob_tmp.select_set(True)
        bpy.context.view_layer.objects.active = ob_tmp
        fp = os.path.join(out_dir, f"{prefix}_{tag}.stl")
        bpy.ops.wm.stl_export(filepath=fp, export_selected_objects=True, apply_modifiers=False, global_scale=1.0)

        bpy.data.objects.remove(ob_tmp, do_unlink=True)
        if me_tmp.users == 0:
            bpy.data.meshes.remove(me_tmp)
        outputs[tag] = (fp, nm, os.path.getsize(fp) / 1024.0)
    bpy.ops.object.select_all(action='DESELECT')
    return outputs

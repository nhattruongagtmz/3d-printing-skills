"""
Example Recipes: Cherry MX Switch Clicker Holder Kit
====================================================
Demonstrates two complete workflows using `scripts/mx_clicker_kit.py`:
  1. `build_preset_puck_clicker()`: Build a round keychain clicker base + cute dome topper from scratch,
     verify 0 non-manifold edges & 4 mm press-travel clearance, and export flat STLs.
  2. `convert_existing_models_to_clicker()`: Inject the MX base socket + MX topper recess/cross-stem
     into any two existing Blender objects (`base_obj`, `topper_obj`).
"""

import os
import sys
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector, Matrix

SKILL_SCRIPTS = str(Path(__file__).resolve().parents[1] / "scripts")
if SKILL_SCRIPTS not in sys.path:
    sys.path.insert(0, SKILL_SCRIPTS)

import mx_clicker_kit as mxk


def build_preset_puck_clicker(out_dir="./mx_puck_clicker_stls"):
    """Workflow A: Generate a complete round keychain clicker + cute dome topper from scratch."""
    # 1. Create a sleek Ø 28 mm round puck base (drop-in 8.3 mm cup + 4.5 mm push-out hole + keychain loop)
    base = mxk.create_round_puck_base(
        name="SM_Puck_Base",
        diameter=28.0,
        height=9.5,
        floor_z=1.2,
        mode="drop_in",
        rot_deg=0.0,
        pushout_hole_r=4.5,
    )
    mxk.attach_keychain_loop(base, side="+Y", outer_r=4.2, hole_r=2.2, thickness=3.6, z_bot=0.0)

    # 2. Create a simple rounded dome topper (Ø 26 mm, height 16 mm, flat bottom at Z = 0)
    col_geo = mxk.get_or_create_collection("COL_Geo", mxk.get_or_create_collection("COL_Project"))
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=28, radius=13.0)
    bmesh.ops.transform(bm, matrix=Matrix.Translation((0.0, 0.0, 6.0)), verts=bm.verts)
    me = bpy.data.meshes.new("SM_Puck_Topper_Mesh")
    bm.to_mesh(me)
    bm.free()
    topper = bpy.data.objects.new("SM_Puck_Topper", me)
    col_geo.objects.link(topper)

    # 3. Slice topper cleanly flat at Z = 0 and carve the exact MX recess + Ø 5.6 post + '+' cross slot!
    mxk.attach_mx_topper_connector(topper, xy=(0.0, 0.0), rot_deg=0.0, slice_flat_z=0.0, auto_skirt=True)

    # 4. Seat topper at realistic resting height (Z = 14.0 mm) for preview & run engineering gates!
    topper.location = Vector((0.0, 0.0, 14.0))
    fit = mxk.verify_mx_fit(base, topper, xy=(0.0, 0.0), rot_deg=0.0)
    travel = mxk.verify_travel_clearance(base, topper, rest_z=14.0, stroke=4.0)
    print("MX Fit Report:", fit)
    print("4 mm Travel Collision Overlaps (0 = PASS):", travel)
    assert fit["base_non_manifold"] == 0 and fit["topper_non_manifold"] == 0
    assert all(v == 0 for v in travel.values()), f"Travel collision detected: {travel}"

    # 5. Export both print-ready flat STLs
    exported = mxk.export_clicker_stls(base, topper, out_dir=out_dir, prefix="puck_clicker")
    print("Exported STLs:", exported)


def convert_existing_models_to_clicker(
    base_name,
    topper_name,
    socket_xy=(0.0, 0.0),
    rot_deg=0.0,
    base_mode="drop_in",
    floor_z=1.2,
    rest_z=14.5,
    out_dir="./custom_clicker_stls",
):
    """Workflow B: Inject MX Base Socket + MX Topper Connector into any existing Blender meshes."""
    base = bpy.data.objects[base_name]
    topper = bpy.data.objects[topper_name]

    mxk.attach_mx_base_socket(base, xy=socket_xy, floor_z=floor_z, rot_deg=rot_deg, mode=base_mode)
    mxk.attach_mx_topper_connector(topper, xy=socket_xy, rot_deg=rot_deg, auto_skirt=True)

    topper.location = Vector((0.0, 0.0, rest_z))
    fit = mxk.verify_mx_fit(base, topper, xy=socket_xy, rot_deg=rot_deg)
    travel = mxk.verify_travel_clearance(base, topper, rest_z=rest_z, stroke=4.0)
    print("MX Fit Report:", fit)
    print("4 mm Travel Collision Overlaps:", travel)
    return mxk.export_clicker_stls(base, topper, out_dir=out_dir, prefix="custom_clicker")


if __name__ == "__main__":
    build_preset_puck_clicker()

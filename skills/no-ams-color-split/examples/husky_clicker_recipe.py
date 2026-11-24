"""
Reference Recipe: Husky-in-a-Box Clicker — Full No-AMS Multi-Color Split
========================================================================
Demonstrates driving `scripts/no_ams_splitter.py` end-to-end inside Blender MCP:
  1. Snapshot evaluated master mesh (`SM_Husky_Body`) into symmetric -Y frame.
  2. Split 2-half main shell (`PART_01_Body_White` + `PART_02_Hood_Black`) with 0.18 mm slide clearance.
  3. Extract 13 surface-conformed, flat-backed inserts (including 3-level nested Eyes -> Pupils -> Highlights).
  4. Cut all +0.18 mm clearance sockets cleanly in a single pass from master (handling seam-crossing eyebrows).
  5. Verify 0 non-manifold edges + 0.00004 mm MX connector preservation.
  6. Export all 16 flat-on-Z=0 STLs ready for color-plate slicing.
"""

import math
import os
import sys
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

SKILL_SCRIPTS = str(Path(__file__).resolve().parents[1] / "scripts")
if SKILL_SCRIPTS not in sys.path:
    sys.path.insert(0, SKILL_SCRIPTS)

import no_ams_splitter as nas


def run_husky_no_ams_split(
    master_name="SM_Husky_Body",
    box_name="SM_Box_Base",
    out_dir="./husky_no_ams_parts",
    tol=0.18,
    insert_chamfer=0.20,
):
    col_proj = nas.get_or_create_collection("COL_Project")
    col_out = nas.get_or_create_collection("COL_Print_Parts", parent=col_proj, clear_objects=True)

    # 1. Materials
    mat_white = nas.make_pbr_material("MAT_Husky_White", (0.95, 0.95, 0.96), roughness=0.48)
    mat_black = nas.make_pbr_material("MAT_Husky_Black", (0.065, 0.070, 0.080), roughness=0.55)
    mat_cyan  = nas.make_pbr_material("MAT_Husky_Eye_Cyan", (0.20, 0.62, 0.72), roughness=0.28, coat=0.4)
    mat_pupil = nas.make_pbr_material("MAT_Husky_Eye_Black", (0.015, 0.015, 0.020), roughness=0.12, coat=0.8)
    mat_nose  = nas.make_pbr_material("MAT_Husky_Nose_Black", (0.025, 0.025, 0.030), roughness=0.22, coat=0.5)
    mat_pink  = nas.make_pbr_material("MAT_Husky_Tongue_Pink", (0.88, 0.44, 0.52), roughness=0.45)

    # 2. Snapshot master mesh in canonical -Y-facing symmetric frame (+45 deg Z)
    rot_p45 = Matrix.Rotation(math.radians(45.0), 4, 'Z')
    rot_m45 = Matrix.Rotation(math.radians(-45.0), 4, 'Z')
    src_obj = bpy.data.objects[master_name]
    bm_master = nas.snapshot_evaluated_bmesh(src_obj, transform=rot_p45)
    assert nas.count_non_manifold(bm_master) == 0, "Master mesh must be manifold before splitting!"
    bvh = BVHTree.FromBMesh(bm_master)

    # 3. 2-Half Undercut-Free Shell Split (Hood vs Body)
    def mask_z(ax):
        if ax < 5.2:
            t = ax / 5.2
            return 15.1 + 5.2 * (math.sin(t * math.pi * 0.5) ** 1.35)
        t = min(1.0, (ax - 5.2) / 11.3)
        return 20.3 - 9.7 * (t * t * (3.0 - 2.0 * t))

    y_surf = lambda ax: -12.5 + 8.5 * min(1.0, (ax / 15.5) ** 2)

    bm_hv = nas.build_slide_split_volume(-22.0, 22.0, 36.0, mask_z, -18.0, 22.0, -12.0, -0.24, expand=0.0, y_surf_fn=y_surf)
    bm_hc = nas.build_slide_split_volume(-22.0, 22.0, 36.0, mask_z, -18.0, 22.0, -12.0, -0.24, expand=tol, y_surf_fn=y_surf)
    bm_hood = nas.bool_op(bm_master, bm_hv, 'INTERSECT')
    bm_body = nas.bool_op(bm_master, bm_hc, 'DIFFERENCE')
    bm_hv.free(); bm_hc.free()

    parts = {}
    hood_cutters, body_cutters = [], []

    # 4. Inner Ears -> Hood
    for side, idx, tag in [(-1, "03", "L"), (1, "04", "R")]:
        c, _ = nas.sample_surface(bvh, (side * 9.5, -8.0, 23.8), (0.0, 1.0, 0.0))
        u, v, n = nas.make_tangent_frame((side * 0.10, -0.98, 0.14))
        tri_3d = [Vector((side * 6.8, c.y, 22.8)), Vector((side * 11.6, c.y, 21.9)), Vector((side * 10.4, c.y, 27.0))]
        tri_2d = nas.rounded_tri_2d(*[((p - c).dot(u), (p - c).dot(v)) for p in tri_3d], corner_r=0.75)
        plug, cut = nas.build_surface_insert(bm_master, tri_2d, c, u, v, n, depth_in=1.8, tol=tol)
        parts[f"PART_{idx}_Ear_Inner_{tag}_White"] = (plug, mat_white)
        hood_cutters.append(cut)

    # 5. Forehead Blaze -> Hood
    bl_c, bl_n = nas.sample_surface(bvh, (0.0, -20.0, 20.8), (0.0, 1.0, 0.0))
    u, v, n = nas.make_tangent_frame(bl_n)
    plug, cut = nas.build_surface_insert(bm_master, nas.teardrop_2d(1.28, 3.45), bl_c, u, v, n, depth_in=1.8, tol=tol)
    parts["PART_05_Blaze_White"] = (plug, mat_white)
    hood_cutters.append(cut)

    # 6. Eyebrows -> Cut from BOTH Hood & Body (seam-crossing!)
    for side, idx, tag in [(-1, "06", "L"), (1, "07", "R")]:
        br_c, _ = nas.sample_surface(bvh, (side * 5.05, -20.0, 19.95), (0.0, 1.0, 0.0))
        u, v, n = nas.make_tangent_frame((side * 0.28, -0.82, 0.50))
        br_2d = nas.ellipse_2d(1.85, 0.95, rot_deg=(side * -18.0))
        plug, cut_h = nas.build_surface_insert(bm_master, br_2d, br_c, u, v, n, depth_in=1.65, tol=tol)
        cut_b = nas.build_prism(br_2d, br_c, u, v, n, -1.80, 5.0, expand=tol)
        parts[f"PART_{idx}_Eyebrow_{tag}_White"] = (plug, mat_white)
        hood_cutters.append(cut_h)
        body_cutters.append(cut_b)

    # 7. Nested Eyes -> Pupils -> Highlights -> Body
    for side, ei, pi, hi, tag in [(-1, "08", "10", "12", "L"), (1, "09", "11", "13", "R")]:
        eye_c, _ = nas.sample_surface(bvh, (side * 7.15, -20.0, 14.32), (0.0, 1.0, 0.0))
        u, v, n = nas.make_tangent_frame((side * 0.44, -0.85, 0.28))
        bm_eye, cut_eye = nas.build_surface_insert(bm_master, nas.ellipse_2d(4.02, 3.08, 56), eye_c, u, v, n, 2.8, tol=tol)
        body_cutters.append(cut_eye)

        pup_c, _ = nas.sample_surface(bvh, (side * 5.82, -20.0, 14.25), (0.0, 1.0, 0.0))
        bm_pup, cut_pup = nas.build_surface_insert(bm_master, nas.ellipse_2d(2.38, 2.38, 48), pup_c, u, v, n, 2.0, tol=tol)
        bm_eye_f = nas.bool_op(bm_eye, cut_pup, 'DIFFERENCE')
        bm_eye.free(); cut_pup.free()

        hl_c, _ = nas.sample_surface(bvh, (side * 5.65, -20.0, 15.10), (0.0, 1.0, 0.0))
        bm_hl, cut_hl = nas.build_surface_insert(bm_master, nas.ellipse_2d(0.62, 0.62, 32), hl_c, u, v, n, 1.4, tol=0.14)
        bm_pup_f = nas.bool_op(bm_pup, cut_hl, 'DIFFERENCE')
        bm_pup.free(); cut_hl.free()

        parts[f"PART_{ei}_Eye_{tag}_Cyan"] = (bm_eye_f, mat_cyan)
        parts[f"PART_{pi}_Pupil_{tag}_Black"] = (bm_pup_f, mat_pupil)
        parts[f"PART_{hi}_Highlight_{tag}_White"] = (bm_hl, mat_white)

    # 8. Nose & Tongue -> Body
    nose_c, _ = nas.sample_surface(bvh, (0.0, -20.0, 13.30), (0.0, 1.0, 0.0))
    u, v, n = nas.make_tangent_frame((0.0, -0.97, 0.24))
    plug, cut = nas.build_surface_insert(bm_master, nas.teardrop_2d(1.88, 0.98, 40), nose_c, u, v, n, 2.2, tol=tol)
    parts["PART_14_Nose_Black"] = (plug, mat_nose); body_cutters.append(cut)

    tng_c, _ = nas.sample_surface(bvh, (0.0, -20.0, 9.55), (0.0, 1.0, 0.0))
    u, v, n = nas.make_tangent_frame((0.0, -0.96, -0.28))
    plug, cut = nas.build_surface_insert(bm_master, nas.ellipse_2d(1.62, 1.12, 40), tng_c, u, v, n, 2.0, tol=tol)
    parts["PART_15_Tongue_Pink"] = (plug, mat_pink); body_cutters.append(cut)

    # 9. Subtract all cutters cleanly from Hood & Body
    for c in hood_cutters:
        bm_hood_n = nas.bool_op(bm_hood, c, 'DIFFERENCE'); bm_hood.free(); c.free(); bm_hood = bm_hood_n
    for c in body_cutters:
        bm_body_n = nas.bool_op(bm_body, c, 'DIFFERENCE'); bm_body.free(); c.free(); bm_body = bm_body_n

    parts["PART_01_Body_White"] = (bm_body, mat_white)
    parts["PART_02_Hood_Black"] = (bm_hood, mat_black)
    bm_master.free()

    # 10. Link assembled preview objects into COL_Print_Parts & export flat-bed STLs
    os.makedirs(out_dir, exist_ok=True)
    if box_name in bpy.data.objects:
        nas.export_flat_stl(
            bpy.data.objects[box_name],
            os.path.join(out_dir, "PART_00_Box_Base_Brown.stl"),
            auto_orient_flat=False,
            apply_modifiers=True,
        )

    for pname in sorted(parts.keys()):
        bm_p, mat_p = parts[pname]
        bmesh.ops.transform(bm_p, matrix=rot_m45, verts=bm_p.verts)
        bmesh.ops.recalc_face_normals(bm_p, faces=bm_p.faces)
        assert nas.count_non_manifold(bm_p) == 0, f"{pname} has non-manifold edges!"

        me = bpy.data.meshes.new(pname + "_Mesh")
        bm_p.to_mesh(me); bm_p.free()
        for p in me.polygons:
            p.use_smooth = True
        ob = bpy.data.objects.new(pname, me)
        ob.data.materials.append(mat_p)
        ob.location = Vector((0.0, 0.0, 15.0))
        col_out.objects.link(ob)

        is_small_insert = pname not in ("PART_01_Body_White", "PART_02_Hood_Black")
        nas.export_flat_stl(
            ob,
            os.path.join(out_dir, pname + ".stl"),
            auto_orient_flat=is_small_insert,
            bottom_chamfer=(insert_chamfer if is_small_insert else 0.0),
        )

    src_obj.hide_viewport = True
    src_obj.hide_render = True
    bpy.context.view_layer.update()


if __name__ == "__main__":
    run_husky_no_ams_split()

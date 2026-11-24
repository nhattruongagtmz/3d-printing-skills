"""
Example Recipe: Paint a Monochrome 3D Husky Mesh Directly From a Reference Photo
================================================================================
Demonstrates driving `scripts/photo_3d_painter.py` inside Blender MCP to:
  1. Project actual pixel colors from a reference photo onto `SM_Husky_Body`.
  2. Quantize pixels in shadow-resistant CIELAB to 4 solid PLA filament colors.
  3. Fill occluded backfaces, enforce symmetry, and denoise speckles.
  4. Export a Bambu Studio / OrcaSlicer-compatible multi-color `.3mf` file.
"""

import sys
from pathlib import Path
import bpy

SKILL_SCRIPTS = str(Path(__file__).resolve().parents[1] / "scripts")
if SKILL_SCRIPTS not in sys.path:
    sys.path.insert(0, SKILL_SCRIPTS)

import photo_3d_painter as p3p


def paint_husky_from_photo(
    obj_name="SM_Husky_Body",
    photo_path="./husky_reference.jpg",
    out_3mf="./husky_painted_ams.3mf",
):
    obj = bpy.data.objects[obj_name]

    palette = [
        {"name": "White", "rgb": (0.95, 0.95, 0.96), "roughness": 0.48, "coat": 0.0},
        {"name": "Black", "rgb": (0.06, 0.065, 0.075), "roughness": 0.50, "coat": 0.1},
        {"name": "Cyan",  "rgb": (0.20, 0.62, 0.72), "roughness": 0.28, "coat": 0.4},
        {"name": "Pink",  "rgb": (0.88, 0.44, 0.52), "roughness": 0.45, "coat": 0.0},
    ]

    stats = p3p.project_photo_to_mesh(
        obj=obj,
        img_path=photo_path,
        palette=palette,
        view_dir=(0.0, -1.0, 0.22),
        canonical_rot_z_deg=45.0,           # Align diagonal (-X,-Y)-facing Husky to -Y
        crop_uv=(0.228, 0.780, 0.480, 0.935),  # Tight Husky head bbox inside boxed photo (above box rim)
        proj_z_range=(7.0, 28.65),          # Visible head above box rim
        min_facing_dot=0.14,
        chroma_weight=1.35,
        lightness_weight=0.75,
        shadow_white_L=58.0,                # Verified studio-lit black-vs-white threshold
        white_name="White",
        black_name="Black",
        symmetry_x=True,
        symmetry_prefer_side="+X",
        back_default_name="Black",
        back_y_threshold=2.0,
        z_floor_override=(6.5, "Black"),
        min_island_faces=120,
        smooth_passes=4,
        protect_names=(),
        sample_radius_px=2,
    )
    print("Projection Stats:", stats)

    exp = p3p.export_multicolor_3mf(obj, out_3mf, apply_modifiers=True, center_z0=True)
    print("Exported Multi-Color 3MF:", exp)
    return stats, exp


if __name__ == "__main__":
    paint_husky_from_photo()

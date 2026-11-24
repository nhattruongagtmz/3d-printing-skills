# Photo-to-3D Projection, CIELAB Tuning & Multi-Color .3MF Specification

## 1. Why CIELAB Beats Raw RGB on Real Photographs
Real photographs of 3D models contain ambient occlusion, rim lighting, and curved shading:
- **White plastic in cheek shadow** often has sRGB `(0.48, 0.48, 0.50)` (`L* ≈ 52, C* ≈ 1`).
- **Matte black plastic in studio highlight** often has sRGB `(0.26, 0.27, 0.29)` (`L* ≈ 29, C* ≈ 2`).
- **Pink tongue in mouth shadow** often has sRGB `(0.62, 0.34, 0.38)` (`L* ≈ 46, a* ≈ +32`).

With raw RGB Euclidean distance, shadowed white frequently flips to black, and shadowed pink flips to dark gray/black.
In **`photo_3d_painter.py`**, we weight **chroma `(a*, b*) = 1.35`** higher than **lightness `L* = 0.75`**, sample a **5×5 median pixel patch (`sample_radius_px=2`)**, and split neutral pixels (`C* < 10`) cleanly at **`shadow_white_L = 58.0`** (verified on real studio-lit black-vs-white plastic: keeps matte black specular sheen at `L* ≈ 45–54` firmly Black while keeping shadowed white plastic at `L* > 60` firmly White!). Adjust down to `48–52` only on very dark/underexposed photos.

---

## 2. Aligning Photos That Contain Other Props (`crop_uv` & `proj_z_range`)
When the reference photo shows the model **inside a box, on a stand, or next to other toys**:
1. Set `proj_z_range = (z_visible_min, z_visible_max)` to the Z range of the mesh visible above the box/stand (e.g., `(7.0, 28.64)` for a Husky head peeking out of a box!).
2. Measure or pass `crop_uv = (u_min, u_max, v_min, v_max)` for the tight bounding box of the target subject in Blender UV space (`v = 0` bottom, `v = 1` top).
3. Match `view_dir` to the camera pitch/yaw in the photo (e.g., `(0.0, -1.0, 0.25)` for a slightly elevated front portrait).
4. Run a 2-second test + `look` close-up; if features (eyes/nose/mouth) sit slightly high/low, nudge `v_min`/`v_max` by `±0.015` and re-run!

---

## 3. Handling Occluded Backfaces & 3/4 Photos
A single front photo cannot see the back of the head or deep side crevices:
- **BVH Occlusion Raycast:** Prevents front-face eyes/mouth from projecting straight through the mesh onto the back of the head.
- **`symmetry_x=True` + `symmetry_prefer_side="+X"` (or `"-X"`):** If the reference photo is slightly angled 3/4 (showing one side more clearly), mirror labels from the better-facing half onto the opposite half for 100% left-right symmetry!
- **`back_default_name` + Geodesic BFS:** Assigns a known solid base color (e.g., `"Black"`) to unseen rear faces (`y > back_y_threshold`), then smoothly flood-fills any remaining hidden crevices from adjacent visible faces.
- **`z_floor_override=(z_limit, color_name)`:** Forces hidden lower mechanical collars/MX bases cleanly to one solid filament color.

---

## 4. Bambu Studio / OrcaSlicer Multi-Color `.3MF` Compatibility
`export_multicolor_3mf()` writes a standard ZIP-packaged `.3mf` containing:
- `[Content_Types].xml` and `_rels/.rels`
- `3D/3dmodel.model` with:
  - `<basematerials id="1">` listing every filament name and `#RRGGBBFF` hex color.
  - Per-triangle `pid="1" p1="<idx>"` (standard 3MF multi-material spec).
  - Optional `paint_color="<hex>"` attribute matching Bambu Studio / OrcaSlicer's `TriangleSelector` single-slot encoding (`"8"` for slot 2, `"C"` for slot 3, `"1C"` for slot 4, `"2C"` for slot 5, etc.).

### Slicer Import Tip
- Drag the exported `.3mf` directly into **Bambu Studio** or **OrcaSlicer**.
- Map each detected filament slot to your loaded AMS spools and slice immediately!
- For **No-AMS (single-extruder) printing**, keep the painted mesh in Blender as your color map and pass it to the **`no-ams-color-split`** skill.

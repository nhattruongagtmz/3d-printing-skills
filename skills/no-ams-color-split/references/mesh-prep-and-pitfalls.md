# Pre-Split Mesh Prep & Hard-Won Blender Pitfalls

This reference documents real failure modes encountered on high-poly (200k–750k face) AI-generated and sculpted meshes in Blender 4.x/5.x via MCP, along with their verified fixes.

---

## 1. Never Skip Visual Inspection (`look`)
- **Failure Mode:** Code prints `non_manifold = 0` while an object silently disappeared, had a thin leftover cap over an eyebrow, or had a 0.8 mm bulge shadow ring.
- **Rule:** After every major mesh prep or Boolean split, run `look` in `solid` shading (which renders `mat.diffuse_color` reliably across Blender 5.x without needing HDRI/lights):
  - Full 6-angle overview (`front`, `3/4`, `left`, `right`, `top`, `back`).
  - Macro close-up (`distance` ≈ 1.2× head width) targeting facial seams, eyes, eyebrows, and any flattened patches.

---

## 2. Fixing Asymmetric / Blurry AI Mesh Halves (`mirror_symmetrize`)
AI 3D generators frequently sculpt one eye/ear crisply while leaving the opposite side blurry or double-lined, and often introduce a 3°–8° head yaw.

- **Wrong Approach:** Projecting/engraving onto coarse irregular triangles (`0.3–0.4 mm` edges) creates jagged "broken" triangles at zoom, or leaves ghost double lines underneath.
- **Correct Approach:**
  1. Measure yaw angle from symmetric outer landmarks (e.g., left vs right ear tips: `yaw = atan2(dy, dx)`).
  2. Rotate `-yaw` around `Z` so the face points dead-straight `-Y`.
  3. Find midline `x_mid` from center landmarks (nose tip / forehead center).
  4. Bisect cleanly at `X = 0` (`dist=1e-5`), duplicate + negate `X` + `reverse_faces`.
  5. **CRITICAL:** Merge seam vertices with **`dist = 0.0001 mm`**, NOT `0.005 mm`! A `0.005 mm` threshold collapses tiny adjacent triangles along dense sculpts and produces 8–20 non-manifold edges. Follow with `dissolve_degenerate(dist=1e-5)`.

---

## 3. Flattening Unwanted Protruding Bumps (`cdt_harmonic_flatten_front_patch`)
When an AI mesh sculpts a flat color marking (like a forehead blaze) as a protruding fin/horn:

- **Trap A — Smoothing/pushing existing bump vertices in Y:** Original bump walls contain dense folded/overhanging triangles. Pushing vertices back leaves pinched wrinkles and shading artifacts.
- **Trap B — Fitting an external polynomial across neighbors:** If nearby protrusions (e.g., sculpted eyebrows) sit inside the fit ring, they pull the fitted surface outward by `0.3–0.8 mm`, leaving a visible raised bulge and shadow rim.
- **Trap C — Radial spoke fan fill (`v_center`):** Connecting 150–200 boundary vertices to one center pole creates skinny needle triangles and visible radial creases.
- **Trap D — `bpy.ops.mesh.fill_grid()` on irregular holes:** Fails whenever boundary edge count is odd or has a concave corner loop.
- **Verified Fix:**
  1. Delete all folded faces inside the bump ellipse.
  2. Sprinkle a uniform `0.25–0.30 mm` 2D interior grid strictly inside the hole.
  3. Stitch with Blender's native `mathutils.geometry.delaunay_2d_cdt` reusing the exact boundary `BMVert`s (zero poles, zero spokes, zero T-junctions).
  4. Run `remove_doubles(boundary, 0.005)` + `holes_fill` to guarantee `non_manifold == 0`.
  5. Run **120 passes of pure harmonic Laplacian smoothing** (`use_axis_y=True` only, then 10 gentle `XYZ` passes) on the uniform interior grid — converges to the exact minimal surface spanning the untouched forehead rim with **0.00 mm step/bulge**.

---

## 4. Exact Boolean Rules on High-Poly Meshes
- **NEVER run `EXACT` Boolean on a mesh containing joined overlapping sub-shells:** Blender's Exact solver can silently drop or invert self-intersecting islands. Keep master geometry as one clean watertight manifold solid (`non_manifold == 0`).
- **NEVER chain adjustment Booleans onto an already-cut shell:** If an insert (like an eyebrow) needs repositioning by `0.5 mm`, **do not** run another `DIFFERENCE` on the already-cut `PART_01_Body_White` (can collapse to empty mesh on dense coplanar cuts). Always re-cut cleanly in a single pass from `bm_master`.
- **Seam-crossing inserts:** Whenever an insert sits within `1.0 mm` of a 2-half shell split boundary, subtract its cutter from **BOTH** adjacent shells during the single clean build pass.
- **Assign dark/correct materials to Boolean cutter meshes** if keeping live Boolean modifiers, because Exact Boolean transfers the cutter's material slot onto newly created cut faces.

---

## 5. Viewport Shading in Blender 5.x via MCP
- In Blender 5.x without a configured world HDRI or studio lighting rig, `look(..., shading="material")` may render tinted/flat red in Eevee preview.
- Use `look(..., shading="solid")` after setting `mat.diffuse_color = (*rgb, 1.0)` on every material — it renders instant, crisp, true-color previews with clear specular shading for catching surface ripples and color seam accuracy.

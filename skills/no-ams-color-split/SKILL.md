---
name: no-ams-color-split
description: >-
  Splits single-mesh 3D models (chibi figurines, keychains, desk toys, AI sculpts, or MX switch clickers)
  in Blender via MCP into interlocking, manifold, flat-backed multi-color STL parts with FDM clearance
  tolerances (default 0.18 mm) for single-extruder / No-AMS 3D printing. Use when the user asks to
  separate colors into printable insert parts, apply Method 1 (Phương án 1 / tách chi tiết khác màu để in riêng),
  carve press-fit sockets, or prepare a multi-color 3D print kit without an AMS/MMU.
license: MIT
metadata:
  version: "1.0.0"
  domain: blender
  role: specialist
  triggers: no-ams, multi-color split, separate color parts, printable inserts, press-fit sockets, phương án 1, tách chi tiết khác màu, in nhiều màu không cần AMS
  related-skills: blender-modeler, asset-optimization, export-pipeline, qa-review
---

# No-AMS Multi-Color 3D Print Splitter

Convert any single-mesh 3D model into a **production-grade, No-AMS interlocking multi-color STL kit** in Blender via MCP. Every part is surface-conformed, watertight (`0` non-manifold edges), given calibrated FDM clearance (`0.18 mm` default), and auto-oriented flat on `Z = 0` for support-free printing.

> **Helper Library:** Load reusable functions directly from [scripts/no_ams_splitter.py](./scripts/no_ams_splitter.py) inside `execute_blender_code` instead of rewriting geometry/Boolean boilerplate from scratch.

---

## Core Architecture

```
1. Inspect & Prep   → Visual audit (look) → Mirror symmetry / CDT bump flatten / trim artifacts
2. Canonical Frame  → Transform master snapshot to symmetric -Y-facing frame (X = 0 midline)
3. Shell Split      → Linearly extruded undercut-free slide volume (0.0 vs +TOL) for 2-half shells
4. Surface Inserts  → Master ∩ Prism(0.0) plugs + Prism(+TOL, +0.15mm deep) socket cutters
5. Nested Inserts   → Cut inner sockets (e.g., Highlight → Pupil → Eye → Body)
6. Mandatory QA     → 0 non-manifold + BVH connector check + macro close-up `look`
7. Auto-Flat Export → Rotate largest flat back face to Z = 0 (+ optional chamfer) → STL plate manifest
```

### Scene Organization
```
COL_Project
├── COL_Reference    # Original STLs / reference meshes (hidden)
├── COL_Geo          # Master single-mesh backup (hidden once split is verified) + Base/Box
├── COL_Components   # Non-destructive Boolean cutters (e.g., MX switch recess/stem)
└── COL_Print_Parts  # Final interlocking color parts (assembled preview at real print coordinates)
```

---

## Step-by-Step Workflow

### Phase 1: Pre-Split Inspection & Mesh Prep
**NEVER split a messy, asymmetric, or bumpy mesh.** Always inspect first with `look` (multi-angle + front close-up).

If the source mesh (especially AI-generated STL) has defects, run the prep helpers from [scripts/no_ams_splitter.py](./scripts/no_ams_splitter.py) (details & pitfalls in [references/mesh-prep-and-pitfalls.md](./references/mesh-prep-and-pitfalls.md)):
- **Blurry / asymmetric side:** `mirror_symmetrize(bm, yaw_landmarks, midline_x)` — aligns yaw, bisects cleanly at `X = 0`, mirrors the crisp side, merges seam at `dist = 0.0001 mm` (never larger!), verifies `non_manifold == 0`.
- **Unwanted protruding sculpt bump (e.g., forehead fin):** `cdt_harmonic_flatten(bm, cx, cz, rx, rz)` — deletes folded bump faces, fills with uniform 2D Constrained Delaunay (`delaunay_2d_cdt`), runs 100+ passes of pure harmonic Laplacian smoothing so the patch sits 100% flush with zero step/shadow ring.
- **Unwanted limbs/debris:** Trim with Exact Boolean `DIFFERENCE` **before** adding base skirts/connectors.

### Phase 2: Snapshot Master & Canonical Alignment
1. Evaluate the master mesh (with all mechanical/base modifiers applied!) into a fresh `bmesh` (`bm_master`). Verify `non_manifold == 0`.
2. Transform `bm_master` into a **canonical `-Y`-facing symmetric frame** (`X = 0` symmetry plane, `+Z` up, bottom at `Z = 0`).
3. Build a `BVHTree` (`bvh_master`) for exact surface raycasting.

### Phase 3: Large Multi-Color Shell Split (Zero-Undercut Slide)
When splitting the main body into 2+ large color shells (e.g., `PART_01_Body_White` + `PART_02_Hood_Black`):
1. Define the 2D front mask curve `mask_z(|x|)` matching the reference image cleanly (zero jagged face-boundary stepping!).
2. Extrude the closed XZ mask profile linearly along an **undercut-free slide vector** (e.g., `dz/dy = -0.24`, sliding straight on from back-top to front-bottom).
3. Keep all mechanical connectors (e.g., MX switch socket at `Z = 0..5.0 mm`) strictly inside the primary base body (`PART_01`).
4. Generate:
   - `Male Shell (Hood)` = `bm_master ∩ SlideVolume(expand=0.0)`
   - `Female Base (Body)` = `bm_master \ SlideVolume(expand=+TOL)`
5. *(Optional)* Add an interlocking registration peg/socket (`add_alignment_pin`) on the mating plane for effortless alignment during gluing.

### Phase 4: Surface-Conformed Flat-Backed Inserts
For every distinct color detail (`Inner Ears`, `Forehead Blaze`, `Eyebrows`, `Eyes`, `Pupils`, `Highlights`, `Nose`, `Tongue`, decals, buttons, etc.):
1. Raycast the center point onto `bvh_master` and build an orthonormal tangent frame `(u, v, n)` with **exact left/right mirror symmetry** for paired parts.
2. Construct a smooth 2D contour (`ellipse_2d`, `teardrop_2d`, `rounded_tri_2d`, or custom polygon) and extrude a prism from `-depth_in` to `+depth_out`.
3. Intersect `bm_master ∩ Prism(expand=0.0)` → yields a **100% flush outer sculpt** with a **guaranteed flat back face** for support-free printing.
4. Build the socket cutter `Prism(expand=+TOL, d_in=-(depth_in + 0.15))` (`+0.15 mm` extra depth for glue/clearance).
5. **Nested parts** (e.g., `Highlight` inside `Pupil` inside `Eye`): subtract inner cutters from outer inserts sequentially before subtracting the outermost cutter from the parent shell.
6. **Seam-crossing parts (CRITICAL):** If an insert lies near the shell split boundary (e.g., eyebrows near a Hood/Body seam), subtract its cutter from **BOTH** parent shells in the **initial single build pass from `bm_master`**.

### Phase 5: Mandatory Verification Gates (DO NOT SKIP)
Run ALL three checks before exporting final STLs:
1. **Manifold Gate:** Every part in `COL_Print_Parts` MUST report `non_manifold == 0` and `verts > 0`.
2. **Mechanical Connector Gate (if applicable):** Run `verify_bvh_connector()` against the reference STL inside the connector zone — require max deviation **`< 0.005 mm`** in both directions.
3. **Visual QA Gate (`look`):**
   - Multi-angle overview (`front`, `3/4`, `left`, `right`, `top`, `back`) in `solid` shading with true material diffuse colors.
   - **Macro close-up** of facial/detail seams (verifies zero missing shells, zero sliver caps on eyebrows/eyes, zero accidental boolean drops).
   - If ANY visual defect appears, **rebuild affected shells cleanly from `bm_master`** (never stack repeated Booleans on an already-cut mesh!).

### Phase 6: Auto-Oriented Flat-Bed STL Export & Plate Manifest
1. For every part:
   - Keep `PART_00` (box/base), `PART_01` (primary body with mechanical base), and upright outer shells (`PART_02`) in their print-bed upright orientation (`Z_min = 0`).
   - Run `export_flat_stl(..., auto_orient_largest_flat=True, chamfer=0.20)` on every small insert so its **largest flat back face lies 100% flush on `Z = 0`** with optional elephant-foot relief chamfer.
2. Name files sequentially with color tags for instant slicer grouping:
   `PART_00_Box_Base_Brown.stl`, `PART_01_Body_White.stl`, `PART_02_Hood_Black.stl`, ...
3. Save both the modular `.blend` file and the `<project>_no_ams_parts/` STL folder.
4. Deliver a **Color-Grouped Print Plate Table** + **Assembly Order Guide** to the user.

---

## Hard Constraints

### MUST DO
- Always work in `1 BU = 1 mm` when round-tripping 3D print STLs.
- Keep `TOL = 0.18 mm` (standard FDM PLA 0.4 mm nozzle) unless the user specifies loose (`0.22–0.25 mm`) or tight (`0.12–0.15 mm`). See [references/tolerances-and-plates.md](./references/tolerances-and-plates.md).
- Always hide `COL_Geo` master mesh (do not delete it) once `COL_Print_Parts` is active.
- Always run `look` close-up verification **after the very last edit** before declaring done.

### MUST NOT DO
- Never use face-material assignment alone as a substitute for geometric separation when the user asks for No-AMS printable parts.
- Never apply chained `EXACT` Booleans onto an already multi-cut mesh when fixing an insert position — always re-cut cleanly from `bm_master`.
- Never export tiny inserts tilted in 3D space — always auto-orient their flat back face onto `Z = 0`.
- Never skip manifold verification (`non_manifold == 0`) on any exported STL.

---

## Reference Files
- **Reusable Python Engine:** [scripts/no_ams_splitter.py](./scripts/no_ams_splitter.py)
- **Mesh Prep & Hard-Won Pitfalls:** [references/mesh-prep-and-pitfalls.md](./references/mesh-prep-and-pitfalls.md)
- **Tolerance Matrix, Chamfers, MX Specs & Print Plates:** [references/tolerances-and-plates.md](./references/tolerances-and-plates.md)
- **Complete End-to-End Example Recipe:** [examples/husky_clicker_recipe.py](./examples/husky_clicker_recipe.py)

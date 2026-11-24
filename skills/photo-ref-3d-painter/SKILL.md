---
name: photo-ref-3d-painter
description: >-
  Automatically paints and color-segments a monochrome 3D print mesh (STL/OBJ/Blender) directly from
  a single reference photograph of that model in Blender via MCP. Uses camera-aligned 2D-to-3D raycast
  projection with BVH occlusion filtering, shadow-resistant CIELAB filament palette quantization,
  optional X-symmetry reinforcement, geodesic backface fill, topological island denoising, boundary
  smoothing, PBR material assignment, and native multi-color .3MF export for Bambu Studio / OrcaSlicer
  (AMS) or handoff to no-ams-color-split. Use when the user asks to color/paint a 3D print model to
  match a specific reference photo.
license: MIT
metadata:
  version: "1.0.0"
  domain: blender
  role: specialist
  triggers: paint 3d model from photo, colorize STL from image, tô màu mẫu in theo ảnh, chiếu màu từ ảnh, 3mf multicolor paint, auto paint filament colors
  related-skills: no-ams-color-split, mx-switch-clicker-kit, blender-modeler, materials, qa-review
---

# Photo-Reference 3D Print Painter

Automatically transfer exact, crisp, solid **filament colors** from a **single reference photograph** onto a monochrome 3D printable mesh in Blender via MCP — producing clean multi-material meshes ready for **Bambu Studio / OrcaSlicer AMS (`.3mf`)** or **No-AMS part splitting (`no-ams-color-split`)**.

> **Helper Library:** Import directly from [scripts/photo_3d_painter.py](./scripts/photo_3d_painter.py) inside `execute_blender_code` (zero external `pip` dependencies — uses native Blender `bpy`, `bmesh`, `mathutils.bvhtree`, `numpy`, and `zipfile`).

---

## Pipeline Overview

```
1. Inspect Photo & Mesh  → Identify physical filament palette (N solid colors) + viewing angle + subject crop
2. Camera Alignment      → Project 3D mesh along matching view_dir → map projected bbox onto photo subject crop
3. Occlusion-Safe Sample → BVH visibility raycast so front pixels NEVER bleed through onto occluded backfaces
4. CIELAB Quantization   → Map sampled pixels to physical filament palette in perceptual Lab space (shadow-safe!)
5. Symmetry & Back Fill  → Mirror crisp lit side (optional) + geodesic BFS flood-fill for unseen back/sides
6. Denoise & Smooth      → Remove speckled micro-islands + smooth jagged boundaries (protecting micro highlights)
7. Visual QA & Export    → Mandatory 6-angle + close-up `look` → Export multi-color `.3mf` or hand off to splitter
```

---

## Step-by-Step Workflow

### Step 1: Analyze Reference Photo & Define Filament Palette
Examine the user's reference photo carefully and define an explicit, compact physical filament palette (`3–8` solid colors, ordered cleanly):
- Example (Husky clicker): `White`, `Black`, `Cyan`, `Pink` (plus optional glossy variants for preview).
- **Avoid gradient bloat:** Physical FDM prints use discrete plastic spools — never quantize into 20 shades of gray. Let CIELAB handle light/shadow variations cleanly.

### Step 2: Match View Direction & Subject Crop Box (`crop_uv`)
1. Estimate the photo's camera direction `view_dir` pointing **from the model toward the camera** (e.g., `(0.0, -1.0, 0.22)` for straight front slightly elevated, or `(-0.7, -0.7, 0.25)` for front-corner 3/4).
2. Determine the subject's normalized UV bounding box `crop_uv = (u_min, u_max, v_min, v_max)` in Blender image coordinates (`v = 0` at bottom, `v = 1` at top):
   - **Clean isolated photo (transparent/solid background):** Pass `crop_uv=None` to auto-detect tight foreground bounds via `auto_detect_subject_crop()`.
   - **Photo containing other props (e.g., character inside a box/stand):** Measure or supply the exact `crop_uv` of the target mesh only (excluding the box/table!) AND optionally set `proj_z_range=(z_min, z_max)` to align strictly to the visible portion of the 3D mesh (e.g., head above the box rim!).

### Step 3: Run Projection, CIELAB Quantization & Cleanup
Call `project_photo_to_mesh(...)` from [scripts/photo_3d_painter.py](./scripts/photo_3d_painter.py):
- **Shadow-Resistant CIELAB (`chroma_weight=1.35`, `shadow_white_L=58.0`):** Neutral gray shadows on white plastic stay **White** while studio key-light sheen on matte black plastic (`L* ≈ 45–54`) stays **Black**; colored accents (pink tongue, cyan eyes) stay crisp even under soft shadow.
- **BVH Occlusion Check:** Every face center is raycast toward the camera; any face facing away (`normal.dot(view_dir) < 0.14`) or blocked by a foreground surface is marked unseen (`-1`).
- **Symmetry Reinforcement (`symmetry_x=True`):** For symmetric characters aligned to `-Y` (`canonical_rot_z_deg`), mirrors labels across `X = 0` (preferring better-lit / seen faces) so slight photo perspective tilts never create asymmetric color drift.
- **Backface & Base Fill:**
  - Unseen back/top regions are filled cleanly via `back_default_idx` (e.g., Black fur on the back of a Husky head) or smooth geodesic BFS propagation from visible boundary colors.
  - Optional `z_floor_override=(z_max, color_idx)` forces hidden lower mechanical collars/skirts (e.g., `Z < 6.5 mm` MX switch base) to a clean solid color.
- **Median Pixel Sampling, Island Denoising & Boundary Smoothing:**
  - `sample_radius_px=2` (5×5 median filter) eliminates single-pixel JPEG/specular noise at sampling time.
  - `min_island_faces=120` removes tiny specular glare islands while preserving valid features (like white eye highlights on dense meshes).
  - `smooth_passes=4` straightens stair-stepped triangle boundaries.

### Step 4: Mandatory Visual QA (`look`)
Run `look(..., shading="solid")` from **6 angles** (`front`, `front-low`, `left-3/4`, `right-3/4`, `top`, `back`) plus a **close-up** of eyes/mouth/seams:
- Verify eyes, pupils, highlights, nose, mouth, and markings align to the sculpted 3D grooves (if offset slightly, adjust `crop_uv` or `view_dir` by `0.01–0.03` and re-run — takes ~3 seconds!).
- Verify zero stray color speckles on forehead, ears, or back of head.

### Step 5: Export for Target 3D Print Workflow
- **AMS / Multi-Material Slicers (Bambu Studio / OrcaSlicer / PrusaSlicer):**
  Call `export_multicolor_3mf(obj, filepath, apply_modifiers=True)` to write a valid `.3mf` archive with `<basematerials>` + per-triangle material indices AND Bambu/Orca `paint_color` attributes!
- **No-AMS Single-Extruder Printing:**
  Hand off the color-mapped mesh directly to the **`no-ams-color-split`** skill to generate interlocking, flat-backed `0.18 mm`-clearance STL parts!

---

## Hard Constraints

### MUST DO
- Always work in `1 BU = 1 mm` and verify `non_manifold == 0` before `.3mf` export.
- Always set `mat.diffuse_color` matching each filament RGB so Blender viewport `solid` shading shows accurate colors.
- Always run a **visual `look` verification** after projection and tune `crop_uv` / `view_dir` if features shift off sculpted grooves.
- Keep `SM_*` backup geometry untouched or save `.blend` after verification.

### MUST NOT DO
- Never compare raw RGB Euclidean distance alone on lit photographs — white plastic in shadow will misclassify as black/gray. Always quantize in **CIELAB** with chroma weighting.
- Never project front pixels onto backfaces without a BVH occlusion + normal-facing check.
- Never export standard `.stl` claiming it carries color — STL is geometry-only; export **`.3mf`** (or split multi-STL via `no-ams-color-split`).

---

## Reference Files
- **Reusable Blender Python Engine:** [scripts/photo_3d_painter.py](./scripts/photo_3d_painter.py)
- **CIELAB Tuning, Occlusion & Bambu `.3mf` Spec:** [references/projection-and-3mf-spec.md](./references/projection-and-3mf-spec.md)
- **End-to-End Example Recipe:** [examples/paint_husky_from_photo.py](./examples/paint_husky_from_photo.py)

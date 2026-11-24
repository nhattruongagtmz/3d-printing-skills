---
name: mx-switch-clicker-kit
description: >-
  Builds and injects Cherry MX mechanical keyboard switch holder kits (Gateron/Kailh/Outemu compatible)
  into any 3D model in Blender via MCP: a lower base square switch socket (drop-in 8.3 mm closed-floor cup
  or snap-in 1.5 mm plate with pin clearance/push-out hole) and an upper topper recessed pocket + Ø 5.6 mm
  cross ('+') stem connector, plus parametric base presets (rounded square, round puck, folded box),
  keychain loops, and automated 4 mm press-travel collision verification. Use when the user asks to
  turn any 3D model into an MX switch fidget clicker, add a switch holder base and cross-stem topper,
  or build a mechanical keycap/clicker kit.
license: MIT
metadata:
  version: "1.0.0"
  domain: blender
  role: specialist
  triggers: mx switch, switch holder, clicker kit, fidget keycap, cross stem, dấu cộng, rãnh vuông switch, ngàm switch cơ, bàn phím cơ clicker
  related-skills: no-ams-color-split, blender-modeler, asset-optimization, export-pipeline
---

# Cherry MX Switch Clicker Holder Kit

Turn **any 3D model** (figurine, chibi head, food prop, custom keycap, desk toy) into a reliable, smooth-clicking **Cherry MX mechanical switch fidget toy** in Blender via MCP.

> **Helper Library:** Import directly from [scripts/mx_clicker_kit.py](./scripts/mx_clicker_kit.py) inside `execute_blender_code` so every switch dimension, clearance recess, cross-stem slot, and travel check is mathematically exact (`1 BU = 1 mm`).

---

## Anatomy of a 2-Part MX Switch Clicker

```
        ┌─────────────────────┐
        │   TOPPER / KEYCAP   │  ← Any 3D character / prop / cap
        │  ┌───────────────┐  │
        │  │  Recess 17.6  │  │  ← 17.6×17.6 mm (R=2.5), depth 5.0 mm
        │  │    ┌─[+]─┐    │  │  ← Ø 5.6 mm stem post + 4.20×1.35 mm '+' slot (depth 4.6 mm)
        └──┴────┴─────┴────┴──┘
                   ↕  4.0 mm click travel (verified collision-free!)
        ┌───┬─────────────┬───┐
        │   │ 14.0 × 14.0 │   │  ← Cherry MX switch housing socket (17.0×17.0 outer, 1.5 mm walls)
        │   │  MX Socket  │   │  ← Mode A: Drop-in 8.3 mm cup (closed 1.2 mm floor) [Default]
        │   └─────────────┘   │  ← Mode B: Snap-in 1.5 mm plate + open/push-out bottom
        └─────────────────────┘
             BASE / HOLDER       ← Custom base OR preset (Square / Round Puck / Folded Box + Keychain)
```

### Scene Organization
```
COL_Project
├── COL_Reference    # Optional reference STLs (hidden)
├── COL_Geo          # Final Base (SM_*_Base) and Topper (SM_*_Topper)
└── COL_Components   # Live non-destructive Boolean cutters (parented to Base/Topper, hidden)
```

---

## Step-by-Step Workflow

### Step 1: Choose or Inspect Base & Topper
- **Existing Base + Topper:** Inspect bounding boxes in mm (`1 BU = 1 mm`), confirm topper's width fits inside any walled base with `≥ 1.0 mm` side clearance.
- **Need a Base Preset?** Generate immediately via [scripts/mx_clicker_kit.py](./scripts/mx_clicker_kit.py):
  - `create_square_base(...)` — compact rounded-square handheld clicker (`24×24 mm` default).
  - `create_round_puck_base(...)` — sleek coin/puck clicker (`Ø 28 mm` default).
  - `create_box_base(...)` — folded-flap cardboard box clicker (`45×45×23.34 mm` MakerWorld standard, `45°` rotated socket).
- **Optional Keychain Loop:** Call `attach_keychain_loop(base_obj, side="+Y", outer_r=4.2, hole_r=2.2, thickness=3.6)` (support-free horizontal eyelet with `2.0 mm` wall strength).

### Step 2: Build Lower Base Switch Housing (`attach_mx_base_socket`)
Choose the mounting mode matching the user's preference (details in [references/mx-switch-engineering.md](./references/mx-switch-engineering.md)):
1. **`mode="drop_in"` (Default):**
   - Unions a `17.0 × 17.0 mm` (`R = 1.0 mm` outer corners), `8.3 mm` tall square cup with a sharp **`14.00 × 14.00 mm`** inner cutout sitting on a `1.2 mm` closed floor.
   - Prints with zero supports, hides metal switch pins safely inside, holds MX switches securely via friction.
   - Optional `pushout_hole_r=4.5` punches a centered bottom finger/tool hole for easy switch swapping.
2. **`mode="snap_in"`:**
   - Creates a true **`1.50 mm`** top clip-plate (`14.00 × 14.00 mm`) over a **`15.60 × 15.60 mm`** lower relief chamber (`6.8 mm` tall) with open bottom (or pin-clearance recess) so the switch's side tabs snap in with a tactile click and metal pins never bottom out.

### Step 3: Build Upper Topper Recess + Cross Stem (`attach_mx_topper_connector`)
Apply directly to any watertight topper object:
1. If the topper is not flat-bottomed, set `slice_flat_z=<height>` to cleanly bisect the bottom flat and reset `Z_min = 0.0`.
2. **Auto-Skirt Protection (`auto_skirt=True`):** Automatically checks whether the topper's `Z = 0..5.0 mm` footprint fully encloses the `17.6 × 17.6 mm` rotated recess with `1.6 mm` minimum wall (`20.8 × 20.8 mm, R = 4.1 mm`). If the topper has a narrow neck/base, cleanly unions `ADD_MX_Topper_Skirt` first!
3. Applies 3 live `EXACT` Boolean modifiers (parented to `topper_obj`, stored hidden in `COL_Components`):
   - `BOOL_Cut_MX_Recess`: `17.60 × 17.60 mm` (`R = 2.50 mm`), depth `Z = 0.0..5.00 mm` (`0.30 mm` radial clearance around `17.0 mm` base housing).
   - `BOOL_Add_MX_Stem_Post`: Cylinder `Ø 5.60 mm` (`R = 2.80 mm`), `Z = 0.0..5.00 mm`.
   - `BOOL_Cut_MX_Cross`: Cross `+` cutout **`4.20 × 1.35 mm`**, depth `Z = 0.0..4.60 mm` (tunable via `cross_arm_w`: `1.30 mm` tight / `1.35 mm` standard / `1.42 mm` loose).
4. **Alignment Rule:** Match `xy` and `rot_deg` identically between `attach_mx_base_socket` and `attach_mx_topper_connector` (e.g., `rot_deg=45.0` for diagonal corner-facing box clickers, `rot_deg=0.0` for straight-facing square/round clickers).

### Step 4: Mandatory Verification Gates (DO NOT SKIP)
1. **Manifold & Dimensional Gate (`verify_mx_fit`):**
   - Confirm **`0` non-manifold edges** on both evaluated Base and evaluated Topper.
   - Verify exact planar cutout/recess/stem measurements (`14.00 mm` base hole, `17.60 mm` topper recess, `Ø 5.60 mm` stem post, `4.20 × 1.35 mm` cross slot).
2. **4 mm Press-Travel Collision Gate (`verify_travel_clearance`):**
   - Simulates pressing the topper straight down by **`4.0 mm`** (checking at `0 mm`, `2 mm`, and `4 mm` depression) using `BVHTree.overlap` to confirm **ZERO unintended wall rubbing or rim collision**!
3. **Visual QA Gate (`look`):**
   - Inspect **bottom view `(0, 0, -1)`** of the Topper (with Base hidden) to verify the rounded-square recess, `Ø 5.6 mm` post, and crisp `+` cross slot are completely unobstructed.
   - Inspect **top view** of the Base to verify the crisp `14.0 × 14.0 mm` square socket.
   - Inspect **assembled 3/4 view** of Base + Topper seated at resting height (`Z ≈ floor_z + 13.5 mm`).

### Step 5: Flat-Bed STL Export (`export_clicker_stls`)
Export both `SM_*_Base.stl` and `SM_*_Topper.stl` flat at `Z = 0` (`apply_modifiers=True`, `global_scale=1.0`, `1 BU = 1 mm`) while preserving the assembled preview in the `.blend` file.

---

## Hard Constraints

### MUST DO
- Always work in `1 BU = 1 mm` (matching slicer millimeters 1:1).
- Keep the exact `xy` offset and `rot_deg` synchronized between Base socket and Topper connector.
- Verify `0` non-manifold edges and run `verify_travel_clearance` before exporting STLs.
- Leave at least `0.40 mm` solid roof above the `4.60 mm` cross slot (recess ceiling at `5.00 mm`) so the topper top never punctures.

### MUST NOT DO
- Never let a child cosmetic mesh (collar, paw, cape, etc.) intrude into `Z = 0.0..5.05 mm` inside the `17.6 × 17.6 mm` topper recess.
- Never omit the `17.6 × 17.6 mm` outer recess around the `+` stem on walled bases — without it, the topper hits the switch housing before completing the `4.0 mm` click stroke!
- Never print the `+` cross slot horizontally on its side — always export the topper upright with its flat connector face resting on `Z = 0`.

---

## Reference Files
- **Reusable Blender CAD Library:** [scripts/mx_clicker_kit.py](./scripts/mx_clicker_kit.py)
- **Cherry MX Specs, Fit Tuning & Engineering Notes:** [references/mx-switch-engineering.md](./references/mx-switch-engineering.md)
- **End-to-End Example Recipes:** [examples/custom_clicker_recipe.py](./examples/custom_clicker_recipe.py)

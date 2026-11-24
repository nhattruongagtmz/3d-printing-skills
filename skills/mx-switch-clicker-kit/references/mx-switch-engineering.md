# Cherry MX Switch Mechanical Engineering Reference (FDM 3D Printing)

## 1. Verified Physical Cherry MX Dimensions

| Feature | Real Cherry MX Spec | 3D-Printed Kit Dimension | Notes |
| :--- | :---: | :---: | :--- |
| **Switch Housing Square** | `13.90 × 13.90 mm` | **`14.00 × 14.00 mm`** | Snug friction fit for Cherry MX, Gateron, Kailh, Outemu. Add `housing_tol=0.05..0.10` if printer over-extrudes. |
| **Upper Rim Flange** | `15.60 × 15.60 mm` | Clears inside **`17.60 × 17.60 mm`** | Topper recess `17.60 mm` clears both the `15.6 mm` flange and the `17.0 mm` base socket walls (`0.30 mm`/side). |
| **Plate Clip Thickness** | `1.50 mm` | **`1.50 mm`** (`snap_in` mode) | Side retention clips snap cleanly below `1.50 mm`. |
| **Lower Body + Pin Depth** | `5.0 mm` body + `3.3 mm` metal pins = **`8.3 mm`** | **`8.30 mm`** (`drop_in` mode) | Drop-in cup (`Z = 1.2..9.5 mm`) fully encloses the body and pins above a solid `1.2 mm` bottom floor! |
| **MX Cross Stem (`+`)** | `4.10 × 1.17 mm` (X) / `1.31 mm` (Y) | **`4.20 × 1.35 mm`** | Symmetric `1.35 mm` arms print cleanly on `0.4 mm` nozzle in both 0° and 45° rotations. |
| **Cross Stem Length** | `3.6 – 4.0 mm` | **`4.60 mm`** slot depth | Extra `0.6 mm` depth ensures the topper never bottoms out prematurely on the stem tip. |
| **Stem Post Outer Dia** | — | **`Ø 5.60 mm`** (`R = 2.80 mm`) | Leaves `≥ 0.70 mm` wall around the `±2.10 mm` cross arms so the stem never splits on press-fit. |
| **Full Click Travel** | `4.00 mm` | Verify **`4.00 mm`** stroke | Topper resting height above base floor is `~13.5–15.0 mm`; fully pressed is `~9.5–11.0 mm`. |

---

## 2. FDM Cross-Stem Fit Tuning (`cross_arm_w`)

Every printer's horizontal hole shrinkage varies slightly by filament & flow rate:

| Fit Feel | `cross_arm_w` | `cross_arm_len` | When to Use |
| :--- | :---: | :---: | :--- |
| **Tight (No Wobble)** | `1.30 mm` | `4.15 mm` | Very well-calibrated Bambu/Prusa with matte PLA (slight firm push to seat). |
| **Standard (Default)** | **`1.35 mm`** | **`4.20 mm`** | **Verified MakerWorld sweet spot** — snaps firmly onto Cherry/Gateron/Kailh stems without cracking the post. |
| **Loose / Easy Swap** | `1.42 mm` | `4.30 mm` | Slightly over-extruding printers, silk PLA, or frequent keycap swapping. |

> **Print Tip:** Always print the topper upright (`Z = 0` flat on the cross-stem face) with **no supports inside the `+` cross slot** (or enable "On build plate only" + support blocker inside the `Ø 5.6 mm` stem post).

---

## 3. Drop-In Cup vs. Snap-In Plate (`mode`)

### Mode A: `"drop_in"` (Default — Best for Desk Toys & Keychains)
- **Pros:** 100% support-free, completely hides sharp copper switch pins underneath a smooth `1.2 mm` closed floor, ultra-strong walls (`1.5 mm`), identical to popular MakerWorld clicker boxes.
- **Tip:** Pass `pushout_hole_r=4.5` if the user wants a small hole underneath to push the switch out later with a pen/hex key.

### Mode B: `"snap_in"` (True Mechanical Keyboard Plate Feel)
- **Pros:** Switch clips in with a crisp snap on a `1.5 mm` upper ledge; open bottom lets you pop switches out effortlessly and works great for ultra-low-profile handheld clickers.
- **Note:** Either snip/bend the 2 copper pins flush if carrying in a pocket, OR keep the base height `≥ 9.5 mm` so the pins remain recessed above the desk surface.

---

## 4. Travel Clearance Math (`verify_travel_clearance`)

When a topper sits inside a walled base (like a cardboard box):
- **Box floor:** `Z = 0.0..1.2 mm`
- **Drop-in socket top:** `Z = 9.5 mm` (switch upper housing sits at `Z ≈ 9.5..15.0 mm`, stem tip at `Z ≈ 18.6 mm`)
- **Topper unpressed resting bottom (`rest_z`):** `Z ≈ 14.0–15.0 mm` (recess ceiling at `Z ≈ 19.0–20.0 mm`)
- **Topper fully pressed bottom (`rest_z - 4.0`):** `Z ≈ 10.0–11.0 mm` (recess ceiling at `Z ≈ 15.0–16.0 mm`, clearing the `9.5 mm` socket top by `≥ 0.5 mm`!)
- **Wall clearance:** Topper horizontal bounding radius inside the box (`Z < box_rim_z`) must be at least **`1.0 mm` smaller** than the box inner wall half-width on every side so angled finger presses never bind against the walls.

---

## 5. Keychain Loop Engineering
- **Minimum ring wall thickness:** `2.0 mm` (`outer_r = 4.2 mm`, `hole_r = 2.2 mm` → `Ø 4.4 mm` hole easily fits standard `6–8 mm` jump rings and lobster clasps).
- **Minimum vertical thickness:** `3.6 mm` (18 layers at `0.2 mm`) so it survives pocket/bag pull forces.
- **Placement:** Keep `z_bot = 0.0` (flush with the build plate!) so the keychain loop prints with **zero overhangs and zero supports**.

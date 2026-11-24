# FDM Tolerances, Shell Splits, Mechanical Connectors & Print Plates

## 1. FDM Clearance Tolerance Presets (0.4 mm Nozzle, PLA)

| Fit Profile | Radial Clearance (`TOL`) | Extra Socket Depth | Best Use Case |
| :--- | :---: | :---: | :--- |
| **Standard Press + Glue (Default)** | **`0.18 mm`** | `+0.15 mm` | Everyday PLA on Bambu/Prusa/Ender (`0.16–0.20 mm` layers); slides in smoothly, lock permanently with a tiny drop of CA superglue. |
| **Micro Pegs (`Ø < 2.0 mm`)** | **`0.14 mm`** | `+0.10 mm` | Tiny eye highlight pegs (`Ø 1.2–1.5 mm`) where `0.18 mm` feels overly loose. |
| **Tight Friction Press-Fit** | `0.12–0.15 mm` | `+0.15 mm` | Calibrated printers (Bambu/Voron with tuned flow/PA) wanting glue-free assembly. |
| **Loose / Easy Hand Fit** | `0.22–0.25 mm` | `+0.20 mm` | Older/uncalibrated printers or PETG/silk PLA with higher swell; requires glue. |

### Recommended Plug Depths (`depth_in`)
- **Large facial inserts (eyes, cheeks, patches > 6 mm):** `2.4 – 3.0 mm`
- **Medium inserts (inner ears, pupils, nose, tongue, blaze):** `1.6 – 2.2 mm`
- **Micro pegs (eye highlights, tiny dots < 2 mm):** `1.2 – 1.5 mm`
- **Bottom elephant-foot relief chamfer (`bottom_chamfer`):** `0.20 – 0.25 mm` on flat-back inserts so first-layer squish never prevents full seating.

---

## 2. Zero-Undercut 2-Half Shell Splitting

To split a rounded character head into a **Front/Lower Base** (`PART_01`) and **Top/Back Hood** (`PART_02`) without overhangs trapping the assembly:

1. Express the desired front-face color mask as a smooth function `mask_z(|x|)` (never follow jagged mesh edges).
2. Choose a straight **slide-on assembly vector** `(0, 1, slide_dz_dy)` — typically `slide_dz_dy = -0.22` to `-0.28` so the rear hood wraps gently down the back of the head while sliding cleanly on/off from behind/above.
3. Compensate the front profile for head curvature `y_surf(|x|)`:
   `z_ref(x) = mask_z(|x|) - slide_dz_dy * (y_surf(|x|) - y_ref)`
4. Intersect `bm_master` with `expand = 0.0` for the Hood (`PART_02`), and subtract `expand = +TOL` from `bm_master` for the Base (`PART_01`).
5. **Large flat mating shells (> 25 mm):** Optionally call `add_alignment_pin(bm_male, bm_female, ...)` (`R = 1.8 mm`, `L = 3.0 mm`, `tol = TOL`) aligned with the slide vector so halves register cleanly while glue cures.

---

## 3. Preserving Mechanical / MX Switch Connectors

When the model has a functional base connector (e.g., Cherry MX fidget clicker keycap):

### Standard Cherry MX Clicker Specs (Verified)
- **Box/Base Socket Cutout:** `14.00 × 14.00 mm` square opening (`1.5 mm` wall thickness, `17.0 × 17.0 mm` outer frame).
- **Keycap Bottom Switch Recess:** `17.60 × 17.60 mm` (`R = 2.5 mm` corners), depth `Z = 0.0..5.0 mm` (`0.30 mm` clearance around `17.0 mm` socket frame).
- **MX Cross-Stem Post:** `Ø 5.60 mm` (`R = 2.80 mm`), `Z = 0.0..5.0 mm`.
- **MX Cross-Stem Slot (`+`):** Arm length `4.20 mm` (`±2.10 mm`), arm width `1.35 mm` (`±0.675 mm`), depth `Z = 0.0..4.60 mm`.

### Preservation Rules
1. Keep the entire mechanical connector zone (`Z = 0.0..5.2 mm`) strictly inside `PART_01` (never let a shell split plane slice through the switch recess or stem!).
2. Verify after splitting with `verify_bvh_zone(bm_part01, bm_ref, in_connector_zone)`:
   - Pass threshold: **`max_err < 0.005 mm`** (typical result: `0.00004 mm`).

---

## 4. Print Plate Grouping & Slicer Checklist

Organize exported STLs by filament color with sequential prefixes (`PART_00`..`PART_NN_<Color>.stl`):

- **Base / Box (`PART_00`):** `0.20 mm` layer height, `2` walls, `15%` gyroid/grid infill, no supports.
- **Primary Body (`PART_01`):** `0.16–0.20 mm` layer height, `2` walls, `15%` infill, flat MX base on `Z = 0`, organic/tree supports on build plate only if cheeks overhang steeply (`> 55°`).
- **Outer Hood (`PART_02`):** `0.16 mm` layer height for smooth dome top layers (enable variable layer height near crown/ear tips), tree supports touching build plate only.
- **Small Flat-Backed Inserts (`PART_03+`):** Auto-oriented with flat back face on `Z = 0` (`face-up`).
  - Layer height: `0.12–0.16 mm` for crisp curved fronts.
  - First layer speed: `20–25 mm/s`; enable `3 mm` outer brim for parts `< 4 mm` (`Highlights`, `Eyebrows`, `Nose`, `Tongue`).
- **Assembly Sequence:** Always assemble **inside-out** (smallest nested inserts → medium inserts → parent shells → final shell slide-on with 1 tiny drop of CA glue on interior mating walls).

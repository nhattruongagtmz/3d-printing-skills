# 3d-printing-skills

Provide useful agent skills for 3D printing workflows (Blender MCP, Cherry MX switch clicker engineering, photo-reference auto-painting, No-AMS multi-color splitting, and print-ready STL/3MF automation).

## Available Skills

| Skill | Path | Description |
| :--- | :--- | :--- |
| **`mx-switch-clicker-kit`** | [skills/mx-switch-clicker-kit](./skills/mx-switch-clicker-kit/SKILL.md) | Builds and injects Cherry MX mechanical switch holder kits (`14×14 mm` drop-in or `1.5 mm` snap-in base sockets + `17.6×17.6 mm` topper clearance recess & `Ø 5.6 mm` / `4.2×1.35 mm` `+` cross stem), parametric base presets (rounded square, round puck, folded box), keychain loops, and 4 mm press-travel collision checks. |
| **`photo-ref-3d-painter`** | [skills/photo-ref-3d-painter](./skills/photo-ref-3d-painter/SKILL.md) | Automatically paints and color-segments a monochrome 3D print mesh directly from a single reference photograph via camera-aligned BVH raycast projection, shadow-resistant CIELAB filament palette quantization, occlusion backface fill, island denoising, and native multi-color `.3mf` export for Bambu Studio / OrcaSlicer (AMS). |
| **`no-ams-color-split`** | [skills/no-ams-color-split](./skills/no-ams-color-split/SKILL.md) | Splits single-mesh 3D models (chibi figurines, keychains, desk toys, AI sculpts, or MX switch clickers) in Blender via MCP into interlocking, manifold, flat-backed multi-color STL parts with FDM clearance tolerances (`0.18 mm` default) for single-extruder / No-AMS 3D printing. |

## Recommended End-to-End Pipeline

```text
Raw 3D Model + Reference Photo
  +-? mx-switch-clicker-kit   (Add Cherry MX base socket & topper cross-stem + 4 mm travel check)
        +-? photo-ref-3d-painter  (Project exact filament colors from reference photo ? .3MF for AMS)
              +-? no-ams-color-split  (Split into flat-backed 0.18 mm press-fit STLs for No-AMS printing)
```

## Installation

Copy any skill folder from `skills/` into your agent's skills directory:

- **Global (Antigravity):** `~/.gemini/config/skills/<skill-name>/`
- **Project-specific:** `<your-workspace>/.agents/skills/<skill-name>/`

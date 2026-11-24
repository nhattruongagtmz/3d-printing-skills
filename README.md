# 3d-printing-skills

Provide useful agent skills for 3D printing workflows (Blender MCP, FDM tolerances, multi-color splitting, MX switch clicker engineering, and print-ready STL automation).

## Available Skills

| Skill | Path | Description |
| :--- | :--- | :--- |
| **`no-ams-color-split`** | [skills/no-ams-color-split](./skills/no-ams-color-split/SKILL.md) | Splits single-mesh 3D models (chibi figurines, keychains, desk toys, AI sculpts, or MX switch clickers) in Blender via MCP into interlocking, manifold, flat-backed multi-color STL parts with FDM clearance tolerances (`0.18 mm` default) for single-extruder / No-AMS 3D printing. |
| **`mx-switch-clicker-kit`** | [skills/mx-switch-clicker-kit](./skills/mx-switch-clicker-kit/SKILL.md) | Builds and injects Cherry MX mechanical switch holder kits (`14×14 mm` drop-in or `1.5 mm` snap-in base sockets + `17.6×17.6 mm` topper clearance recess & `Ø 5.6 mm` / `4.2×1.35 mm` `+` cross stem), parametric base presets (rounded square, round puck, folded box), keychain loops, and 4 mm press-travel collision checks. |

## Installation

Copy any skill folder from `skills/` into your agent's skills directory:

- **Global (Antigravity):** `~/.gemini/config/skills/<skill-name>/`
- **Project-specific:** `<your-workspace>/.agents/skills/<skill-name>/`

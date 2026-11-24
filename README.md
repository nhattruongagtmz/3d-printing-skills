# 3d-printing-skills

Provide useful agent skills for 3D printing workflows (Blender MCP, FDM tolerances, multi-color splitting, and print-ready STL automation).

## Available Skills

| Skill | Path | Description |
| :--- | :--- | :--- |
| **`no-ams-color-split`** | [skills/no-ams-color-split](./skills/no-ams-color-split/SKILL.md) | Splits single-mesh 3D models (chibi figurines, keychains, desk toys, AI sculpts, or MX switch clickers) in Blender via MCP into interlocking, manifold, flat-backed multi-color STL parts with FDM clearance tolerances (`0.18 mm` default) for single-extruder / No-AMS 3D printing. |

## Installation

Copy a skill folder from `skills/` into your agent's skills directory:

- **Global (Antigravity):** `~/.gemini/config/skills/<skill-name>/`
- **Project-specific:** `<your-workspace>/.agents/skills/<skill-name>/`

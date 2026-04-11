"""3D graph plugin configuration for Obsidian.

Generates config for the "3D Graph" community plugin
(https://github.com/Apoo711/obsidian-3d-graph) so branches and
communities are color-coded in the 3D force-directed layout.
"""

from __future__ import annotations

import json
from pathlib import Path

from ramets.obsidian.vault import COMMUNITY_COLORS

# 3D graph plugin metadata
_PLUGIN_ID = "3d-graph"
_PLUGIN_NAME = "3D Graph"
_PLUGIN_VERSION = "1.0.0"


def generate_3d_config(
    vault_dir: Path,
    communities: dict[int, list[dict]],
    branches: list[str] | None = None,
) -> None:
    """Generate 3D graph plugin config with community and branch coloring.

    Args:
        vault_dir: Root of the Obsidian vault.
        communities: Community ID -> list of node dicts.
        branches: Branch names to assign distinct colors.
    """
    plugin_dir = vault_dir / ".obsidian" / "plugins" / _PLUGIN_ID
    plugin_dir.mkdir(parents=True, exist_ok=True)

    _write_manifest(plugin_dir)
    _write_data(plugin_dir, communities, branches)
    _write_styles(plugin_dir)


def _write_manifest(plugin_dir: Path) -> None:
    """Write manifest.json so Obsidian recognises the plugin folder."""
    manifest = {
        "id": _PLUGIN_ID,
        "name": _PLUGIN_NAME,
        "version": _PLUGIN_VERSION,
        "description": "3D force-directed graph for ramets knowledge graphs",
        "isDesktopOnly": True,
    }
    (plugin_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def _write_data(
    plugin_dir: Path,
    communities: dict[int, list[dict]],
    branches: list[str] | None,
) -> None:
    """Write data.json with color groups for communities and branches."""
    groups = []

    # Community color groups
    for i, cid in enumerate(sorted(communities.keys())[:20]):
        color = COMMUNITY_COLORS[i % len(COMMUNITY_COLORS)]
        groups.append(
            {
                "query": f"tag:community/C{cid:02d}",
                "color": color,
            }
        )

    # Branch-specific colors (gold-tinted for branch layers)
    branch_colors = ["#FFD700", "#FFA500", "#FF6347", "#00CED1", "#7B68EE"]
    for i, br in enumerate((branches or [])[:5]):
        sanitized = br.replace("/", "--").replace("\\", "--")
        groups.append(
            {
                "query": f"tag:branch/{sanitized}",
                "color": branch_colors[i % len(branch_colors)],
            }
        )

    # Decision notes in gold
    groups.append(
        {
            "query": "tag:layer/decision",
            "color": "#FFD700",
        }
    )

    # Superseded decisions faded
    groups.append(
        {
            "query": "tag:decision status:superseded",
            "color": "#808080",
        }
    )

    data = {
        "colorGroups": groups,
        "nodeSize": 5,
        "linkWidth": 1,
        "particleCount": 0,
        "focusOnHover": True,
        "showLabels": True,
        "dagMode": "",
    }

    (plugin_dir / "data.json").write_text(json.dumps(data, indent=2) + "\n")


def _write_styles(plugin_dir: Path) -> None:
    """Write styles.css stub for the plugin."""
    css = """\
/* ramets 3D graph plugin styles */
.graph-3d-container {
    background: #1a1a2e;
}
"""
    (plugin_dir / "styles.css").write_text(css)

"""Claude Desktop MCP server configuration.

Generates/updates claude_desktop_config.json so Desktop connects to
the ramets MCP server via stdio. Also writes a CLAUDE.md project
instruction telling Desktop to call session_summary on session start.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path


def _desktop_config_path() -> Path:
    """Return the platform-specific path to claude_desktop_config.json."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "win32":
        appdata = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
        return Path(appdata) / "Claude" / "claude_desktop_config.json"
    else:
        # Linux / other
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def _resolve_command() -> tuple[str, list[str]]:
    """Pick the best command to launch ramets serve.

    If ``ramets`` is on PATH, use it directly.
    Otherwise fall back to ``sys.executable -m ramets``.
    """
    if shutil.which("ramets"):
        return "ramets", ["serve"]
    return sys.executable, ["-m", "ramets", "serve"]


def install_desktop_config(repo_path: Path) -> Path:
    """Add or update the ramets MCP server entry in Desktop config.

    Performs a read-modify-write so existing MCP servers are preserved.
    Returns the path to the config file.
    """
    config_path = _desktop_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if config_path.exists():
        config = json.loads(config_path.read_text())
    else:
        config = {}

    servers = config.setdefault("mcpServers", {})
    command, args = _resolve_command()

    servers["ramets"] = {
        "command": command,
        "args": args,
        "cwd": str(repo_path),
    }

    config_path.write_text(json.dumps(config, indent=2) + "\n")
    return config_path


def uninstall_desktop_config() -> Path | None:
    """Remove the ramets entry from Desktop config.

    Returns the config path if it was modified, None if no config exists.
    """
    config_path = _desktop_config_path()
    if not config_path.exists():
        return None

    config = json.loads(config_path.read_text())
    servers = config.get("mcpServers", {})

    if "ramets" not in servers:
        return None

    del servers["ramets"]
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    return config_path


# ── Project instruction for Desktop ──────────────────────────────

_CLAUDE_MD_SECTION = """\

# ramets — automatic context injection
At the start of every conversation about this codebase, call the \
session_summary MCP tool first to get branch-aware context (~400 tokens).
"""


def install_project_instruction(repo_path: Path) -> bool:
    """Append ramets instruction to repo-root CLAUDE.md if not present.

    Returns True if the file was modified.
    """
    claude_md = repo_path / "CLAUDE.md"

    if claude_md.exists():
        content = claude_md.read_text()
        if "session_summary" in content:
            return False
        with open(claude_md, "a") as f:
            f.write(_CLAUDE_MD_SECTION)
        return True

    claude_md.write_text(_CLAUDE_MD_SECTION.lstrip())
    return True

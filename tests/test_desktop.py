"""Tests for Claude Desktop MCP config generation."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from ramets.hooks.desktop import (
    _desktop_config_path,
    install_desktop_config,
    install_project_instruction,
    uninstall_desktop_config,
)


class TestDesktopConfigPath:
    def test_macos(self):
        with patch.object(sys, "platform", "darwin"):
            p = _desktop_config_path()
            assert "Application Support" in str(p)
            assert p.name == "claude_desktop_config.json"

    def test_linux(self):
        with patch.object(sys, "platform", "linux"):
            p = _desktop_config_path()
            assert ".config/Claude" in str(p)
            assert p.name == "claude_desktop_config.json"

    def test_windows(self):
        with (
            patch.object(sys, "platform", "win32"),
            patch.dict("os.environ", {"APPDATA": "/fake/appdata"}),
        ):
            p = _desktop_config_path()
            assert "fake" in str(p) or "APPDATA" in str(p) or "Claude" in str(p)
            assert p.name == "claude_desktop_config.json"


class TestInstallDesktopConfig:
    def test_creates_new_config(self, tmp_path: Path):
        config_path = tmp_path / "claude_desktop_config.json"
        repo = tmp_path / "myrepo"
        repo.mkdir()

        with patch("ramets.hooks.desktop._desktop_config_path", return_value=config_path):
            result = install_desktop_config(repo)

        assert result == config_path
        config = json.loads(config_path.read_text())
        assert "ramets" in config["mcpServers"]
        server = config["mcpServers"]["ramets"]
        assert "serve" in server["args"]
        assert server["cwd"] == str(repo)

    def test_preserves_existing_servers(self, tmp_path: Path):
        config_path = tmp_path / "claude_desktop_config.json"
        config_path.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "other-tool": {"command": "other", "args": ["run"]},
                    }
                }
            )
        )
        repo = tmp_path / "myrepo"
        repo.mkdir()

        with patch("ramets.hooks.desktop._desktop_config_path", return_value=config_path):
            install_desktop_config(repo)

        config = json.loads(config_path.read_text())
        assert "other-tool" in config["mcpServers"]
        assert "ramets" in config["mcpServers"]

    def test_idempotent(self, tmp_path: Path):
        config_path = tmp_path / "claude_desktop_config.json"
        repo = tmp_path / "myrepo"
        repo.mkdir()

        with patch("ramets.hooks.desktop._desktop_config_path", return_value=config_path):
            install_desktop_config(repo)
            install_desktop_config(repo)

        config = json.loads(config_path.read_text())
        assert len(config["mcpServers"]) == 1

    def test_creates_parent_dirs(self, tmp_path: Path):
        config_path = tmp_path / "deep" / "nested" / "claude_desktop_config.json"
        repo = tmp_path / "myrepo"
        repo.mkdir()

        with patch("ramets.hooks.desktop._desktop_config_path", return_value=config_path):
            install_desktop_config(repo)

        assert config_path.exists()


class TestUninstallDesktopConfig:
    def test_removes_ramets_only(self, tmp_path: Path):
        config_path = tmp_path / "claude_desktop_config.json"
        config_path.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "ramets": {"command": "ramets", "args": ["serve"]},
                        "other": {"command": "other", "args": []},
                    }
                }
            )
        )

        with patch("ramets.hooks.desktop._desktop_config_path", return_value=config_path):
            result = uninstall_desktop_config()

        assert result == config_path
        config = json.loads(config_path.read_text())
        assert "ramets" not in config["mcpServers"]
        assert "other" in config["mcpServers"]

    def test_no_config_file(self, tmp_path: Path):
        config_path = tmp_path / "nonexistent.json"
        with patch("ramets.hooks.desktop._desktop_config_path", return_value=config_path):
            assert uninstall_desktop_config() is None

    def test_no_ramets_entry(self, tmp_path: Path):
        config_path = tmp_path / "claude_desktop_config.json"
        config_path.write_text(json.dumps({"mcpServers": {"other": {}}}))

        with patch("ramets.hooks.desktop._desktop_config_path", return_value=config_path):
            assert uninstall_desktop_config() is None


class TestProjectInstruction:
    def test_creates_new_claude_md(self, tmp_path: Path):
        assert install_project_instruction(tmp_path) is True
        claude_md = tmp_path / "CLAUDE.md"
        assert claude_md.exists()
        assert "session_summary" in claude_md.read_text()

    def test_appends_to_existing(self, tmp_path: Path):
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Existing content\nSome rules here.\n")

        assert install_project_instruction(tmp_path) is True
        content = claude_md.read_text()
        assert "Existing content" in content
        assert "session_summary" in content

    def test_skips_if_already_present(self, tmp_path: Path):
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("Already has session_summary instruction.\n")

        assert install_project_instruction(tmp_path) is False

    def test_idempotent(self, tmp_path: Path):
        install_project_instruction(tmp_path)
        install_project_instruction(tmp_path)

        content = (tmp_path / "CLAUDE.md").read_text()
        assert content.count("session_summary") == 1

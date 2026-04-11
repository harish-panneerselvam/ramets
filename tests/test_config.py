"""Tests for decision config (decision/config.py)."""

import json

import pytest

from ramets.decision.config import (
    AutoDecisionConfig,
    load_config,
    save_config,
    save_default_config,
)


@pytest.fixture
def repo(tmp_path):
    """Create a repo-like directory with .ramets/."""
    ramets_dir = tmp_path / ".ramets"
    ramets_dir.mkdir()
    return tmp_path


class TestLoadConfig:
    def test_defaults_when_missing(self, repo):
        """Returns defaults when no config file exists."""
        cfg = load_config(repo)
        assert cfg.strategy == "commit-mining"
        assert cfg.commit_mining.enabled is True
        assert cfg.commit_mining.min_confidence == 0.5
        assert cfg.claude_instruction.enabled is False
        assert cfg.session_end.enabled is False

    def test_defaults_when_invalid_json(self, repo):
        """Returns defaults for invalid JSON."""
        (repo / ".ramets" / "config.json").write_text("not json")
        cfg = load_config(repo)
        assert cfg.strategy == "commit-mining"

    def test_loads_custom_values(self, repo):
        """Loads custom config values."""
        config = {
            "auto_decisions": {
                "strategy": "session-end",
                "commit_mining": {"enabled": False, "min_confidence": 0.3},
                "claude_instruction": {"enabled": True},
                "session_end": {"enabled": True},
            }
        }
        (repo / ".ramets" / "config.json").write_text(json.dumps(config))
        cfg = load_config(repo)
        assert cfg.strategy == "session-end"
        assert cfg.commit_mining.enabled is False
        assert cfg.commit_mining.min_confidence == 0.3
        assert cfg.claude_instruction.enabled is True
        assert cfg.session_end.enabled is True

    def test_partial_config_gets_defaults(self, repo):
        """Partial config fills in defaults for missing fields."""
        config = {"auto_decisions": {"strategy": "custom"}}
        (repo / ".ramets" / "config.json").write_text(json.dumps(config))
        cfg = load_config(repo)
        assert cfg.strategy == "custom"
        assert cfg.commit_mining.enabled is True  # default


class TestSaveConfig:
    def test_round_trip(self, repo):
        """Save then load produces same config."""
        cfg = AutoDecisionConfig(strategy="session-end")
        cfg.session_end.enabled = True
        save_config(repo, cfg)
        loaded = load_config(repo)
        assert loaded.strategy == "session-end"
        assert loaded.session_end.enabled is True

    def test_preserves_existing_keys(self, repo):
        """Save doesn't clobber unrelated keys."""
        existing = {"custom_key": "preserved", "auto_decisions": {"strategy": "old"}}
        (repo / ".ramets" / "config.json").write_text(json.dumps(existing))

        cfg = AutoDecisionConfig(strategy="new")
        save_config(repo, cfg)

        raw = json.loads((repo / ".ramets" / "config.json").read_text())
        assert raw["custom_key"] == "preserved"
        assert raw["auto_decisions"]["strategy"] == "new"

    def test_creates_directory(self, tmp_path):
        """Save creates .ramets/ if needed."""
        cfg = AutoDecisionConfig()
        path = save_config(tmp_path, cfg)
        assert path.exists()


class TestSaveDefaultConfig:
    def test_creates_default(self, repo):
        """Creates default config when none exists."""
        path = save_default_config(repo)
        assert path.exists()
        cfg = load_config(repo)
        assert cfg.commit_mining.enabled is True

    def test_no_overwrite(self, repo):
        """Doesn't overwrite existing config."""
        custom = {"auto_decisions": {"strategy": "custom"}}
        config_path = repo / ".ramets" / "config.json"
        config_path.write_text(json.dumps(custom))

        save_default_config(repo)
        cfg = load_config(repo)
        assert cfg.strategy == "custom"

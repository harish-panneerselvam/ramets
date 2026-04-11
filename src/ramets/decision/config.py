"""Configuration for auto-decision capture.

Manages `.ramets/config.json` with per-repo settings for decision
mining strategies: commit-mining (0 tokens), claude-instruction (~50),
and session-end (~100).
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class CommitMiningConfig(BaseModel):
    enabled: bool = True
    min_confidence: float = 0.5
    ignore_prefixes: list[str] = Field(default_factory=lambda: ["chore", "ci", "docs", "style"])


class ClaudeInstructionConfig(BaseModel):
    enabled: bool = False


class SessionEndConfig(BaseModel):
    enabled: bool = False


class AutoDecisionConfig(BaseModel):
    strategy: str = "commit-mining"
    commit_mining: CommitMiningConfig = Field(default_factory=CommitMiningConfig)
    claude_instruction: ClaudeInstructionConfig = Field(default_factory=ClaudeInstructionConfig)
    session_end: SessionEndConfig = Field(default_factory=SessionEndConfig)


class RametsConfig(BaseModel):
    auto_decisions: AutoDecisionConfig = Field(default_factory=AutoDecisionConfig)


def load_config(repo_path: Path) -> AutoDecisionConfig:
    """Load auto-decision config from `.ramets/config.json`.

    Returns defaults if the file doesn't exist or is invalid.
    """
    config_path = repo_path / ".ramets" / "config.json"
    if not config_path.exists():
        return AutoDecisionConfig()

    try:
        data = json.loads(config_path.read_text())
        full = RametsConfig.model_validate(data)
        return full.auto_decisions
    except (json.JSONDecodeError, Exception):
        return AutoDecisionConfig()


def save_config(repo_path: Path, config: AutoDecisionConfig) -> Path:
    """Write config to `.ramets/config.json`. Returns path."""
    config_path = repo_path / ".ramets" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Preserve any existing keys outside auto_decisions
    existing: dict = {}
    if config_path.exists():
        try:
            existing = json.loads(config_path.read_text())
        except json.JSONDecodeError:
            pass

    existing["auto_decisions"] = config.model_dump()
    config_path.write_text(json.dumps(existing, indent=2) + "\n")
    return config_path


def save_default_config(repo_path: Path) -> Path:
    """Write the default config if none exists. Returns path."""
    config_path = repo_path / ".ramets" / "config.json"
    if config_path.exists():
        return config_path
    return save_config(repo_path, AutoDecisionConfig())

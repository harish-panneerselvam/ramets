"""Pydantic models for the decision graph."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DecisionCategory(str, Enum):
    architecture = "architecture"
    implementation = "implementation"
    dependency = "dependency"
    naming = "naming"
    algorithm = "algorithm"
    refactor = "refactor"
    config = "config"
    test_strategy = "test_strategy"
    api_design = "api_design"
    data_model = "data_model"
    performance = "performance"
    security = "security"


class DecisionStatus(str, Enum):
    active = "active"
    superseded = "superseded"
    reversed = "reversed"
    deferred = "deferred"


class Proposer(str, Enum):
    claude = "claude"
    cursor = "cursor"
    codex = "codex"
    copilot = "copilot"
    user = "user"


class DecisionRelation(str, Enum):
    led_to = "led_to"
    supersedes = "supersedes"
    conflicts_with = "conflicts_with"
    depends_on = "depends_on"
    implemented_in = "implemented_in"
    reverted_by = "reverted_by"
    informed_by = "informed_by"


class Option(BaseModel):
    """One option in a decision."""

    label: str
    description: str = ""
    proposed_by: Proposer = Proposer.user
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    estimated_effort: str = ""  # trivial, small, medium, large, epic


class Decision(BaseModel):
    """A structured record of a design/implementation decision."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    branch: str
    session_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    category: DecisionCategory
    question: str
    options: list[Option]
    chosen: int  # index into options
    rationale: Optional[str] = None
    confidence: Optional[float] = None  # 0.0-1.0
    status: DecisionStatus = DecisionStatus.active
    superseded_by: Optional[str] = None
    context_files: list[str] = Field(default_factory=list)
    commit_sha: Optional[str] = None

    @property
    def chosen_option(self) -> Option:
        """Get the chosen option."""
        return self.options[self.chosen]

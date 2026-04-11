"""Commit message mining for automatic decision capture.

Parses git commit messages using regex patterns to extract structured
decisions. Zero LLM tokens — pure local text processing.
"""

from __future__ import annotations

import re

from ramets.decision.schema import Decision, DecisionCategory, Option

# Conventional commit prefix → decision category
PREFIX_CATEGORY: dict[str, DecisionCategory | None] = {
    "feat": DecisionCategory.implementation,
    "fix": DecisionCategory.implementation,
    "refactor": DecisionCategory.refactor,
    "perf": DecisionCategory.performance,
    "build": DecisionCategory.dependency,
    "deps": DecisionCategory.dependency,
    "test": DecisionCategory.test_strategy,
    "style": None,  # skip
    "docs": None,
    "ci": None,
    "chore": None,
}

# Regex for conventional commit: type(scope): description
_CONVENTIONAL_RE = re.compile(
    r"^(?P<prefix>[a-z]+)(?:\([^)]*\))?[!]?:\s*(?P<desc>.+)", re.IGNORECASE
)

# Decision patterns (ordered by specificity)
_PATTERNS: list[tuple[re.Pattern, str, float]] = [
    # "chose X over Y"
    (
        re.compile(r"chos[e]?\s+(.+?)\s+over\s+(.+?)(?:\s+(?:for|because|since)|$)", re.I),
        "choice",
        0.9,
    ),
    # "switch/migrate from X to Y" or "replace X with Y"
    (
        re.compile(r"(?:switch(?:ed)?|migrat(?:e|ed))\s+from\s+(.+?)\s+to\s+(.+?)(?:\s|$)", re.I),
        "switch",
        0.8,
    ),
    (
        re.compile(r"replac(?:e|ed)\s+(.+?)\s+with\s+(.+?)(?:\s|$)", re.I),
        "switch",
        0.8,
    ),
    # "extract X from/into Y"
    (
        re.compile(r"extract(?:ed)?\s+(.+?)\s+(?:from|into|out\s+of)\s+(.+?)(?:\s|$)", re.I),
        "extract",
        0.7,
    ),
    # "add/use/adopt/introduce X"
    (
        re.compile(r"(?:add|use|adopt|introduce)\s+(.+?)(?:\s+(?:for|to|as|in)|$)", re.I),
        "adopt",
        0.6,
    ),
]

# Merge commit patterns to skip
_MERGE_RE = re.compile(r"^Merge\s+(?:branch|pull|remote)", re.I)


def mine_commit(
    message: str,
    branch: str,
    commit_sha: str,
    changed_files: list[str],
    min_confidence: float = 0.5,
    ignore_prefixes: list[str] | None = None,
) -> list[Decision]:
    """Extract decisions from a commit message.

    Args:
        message: Full commit message (subject + body).
        branch: Current branch name.
        commit_sha: Short commit SHA.
        changed_files: Files changed in the commit.
        min_confidence: Minimum confidence threshold to include.
        ignore_prefixes: Conventional commit prefixes to skip.

    Returns:
        List of Decision objects (may be empty).
    """
    if not message or not message.strip():
        return []

    subject = message.strip().split("\n")[0].strip()

    # Skip merge commits
    if _MERGE_RE.match(subject):
        return []

    if ignore_prefixes is None:
        ignore_prefixes = ["chore", "ci", "docs", "style"]

    # Parse conventional commit format
    conv_match = _CONVENTIONAL_RE.match(subject)
    prefix = None
    description = subject

    if conv_match:
        prefix = conv_match.group("prefix").lower()
        description = conv_match.group("desc").strip()

        # Skip ignored prefixes
        if prefix in ignore_prefixes:
            return []

    # Determine base category from prefix
    category = DecisionCategory.implementation
    if prefix and prefix in PREFIX_CATEGORY:
        cat = PREFIX_CATEGORY[prefix]
        if cat is None:
            return []
        category = cat

    # Try decision patterns on the description
    for pattern, kind, confidence in _PATTERNS:
        m = pattern.search(description)
        if not m:
            continue

        if confidence < min_confidence:
            continue

        decision = _build_decision(
            kind, m, description, category, branch, commit_sha, changed_files, confidence
        )
        if decision:
            return [decision]

    # Fallback for conventional commits with meaningful prefixes
    if prefix and prefix not in ignore_prefixes and PREFIX_CATEGORY.get(prefix) is not None:
        if 0.4 >= min_confidence:
            return [
                Decision(
                    branch=branch,
                    category=category,
                    question=description,
                    options=[Option(label=description)],
                    chosen=0,
                    confidence=0.4,
                    context_files=changed_files[:10],
                    commit_sha=commit_sha,
                )
            ]

    # Non-conventional fallback: low-confidence note
    if not prefix and len(subject.split()) > 5 and not _MERGE_RE.match(subject):
        # Apply patterns even without conventional prefix
        for pattern, kind, confidence in _PATTERNS:
            m = pattern.search(subject)
            if not m:
                continue
            decision = _build_decision(
                kind, m, subject, category, branch, commit_sha, changed_files, confidence
            )
            if decision and decision.confidence >= min_confidence:
                return [decision]

        # Record as very low-confidence note
        if 0.2 >= min_confidence:
            return [
                Decision(
                    branch=branch,
                    category=DecisionCategory.implementation,
                    question=subject,
                    options=[Option(label=subject)],
                    chosen=0,
                    confidence=0.2,
                    context_files=changed_files[:10],
                    commit_sha=commit_sha,
                )
            ]

    return []


def _build_decision(
    kind: str,
    match: re.Match,
    description: str,
    category: DecisionCategory,
    branch: str,
    commit_sha: str,
    changed_files: list[str],
    confidence: float,
) -> Decision | None:
    """Build a Decision from a regex match."""
    groups = match.groups()

    if kind == "choice" and len(groups) >= 2:
        chosen_label = groups[0].strip()
        rejected_label = groups[1].strip()
        return Decision(
            branch=branch,
            category=category,
            question=f"{description}?",
            options=[
                Option(label=chosen_label),
                Option(label=rejected_label),
            ],
            chosen=0,
            confidence=confidence,
            rationale=f"Chose {chosen_label} over {rejected_label}",
            context_files=changed_files[:10],
            commit_sha=commit_sha,
        )

    if kind == "switch" and len(groups) >= 2:
        old = groups[0].strip()
        new = groups[1].strip()
        return Decision(
            branch=branch,
            category=category,
            question=f"Switch from {old}?",
            options=[
                Option(label=old),
                Option(label=new),
            ],
            chosen=1,
            confidence=confidence,
            rationale=f"Switched from {old} to {new}",
            context_files=changed_files[:10],
            commit_sha=commit_sha,
        )

    if kind == "extract" and len(groups) >= 2:
        extracted = groups[0].strip()
        source = groups[1].strip()
        return Decision(
            branch=branch,
            category=DecisionCategory.architecture,
            question=f"Extract {extracted} from {source}?",
            options=[
                Option(label=f"Extract {extracted}"),
                Option(label=f"Keep in {source}"),
            ],
            chosen=0,
            confidence=confidence,
            rationale=f"Extracted {extracted} from {source}",
            context_files=changed_files[:10],
            commit_sha=commit_sha,
        )

    if kind == "adopt" and len(groups) >= 1:
        adopted = groups[0].strip()
        return Decision(
            branch=branch,
            category=category,
            question=f"Use {adopted}?",
            options=[Option(label=adopted)],
            chosen=0,
            confidence=confidence,
            rationale=f"Adopted {adopted}",
            context_files=changed_files[:10],
            commit_sha=commit_sha,
        )

    return None

"""Claude Code hook generator.

Generates .claude/settings.json entries and hook scripts for:
- SessionStart: inject branch-aware graph summary (~400 tokens)
- UserPromptSubmit: detect architecture questions, redirect to ramets query
- PreToolUse: gate expensive reads, suggest graph traversal
"""

from __future__ import annotations

import json
import stat
from pathlib import Path
from textwrap import dedent

from ramets.core.branch import get_main_repo_root


def install_claude_hooks(repo_path: Path | None = None) -> None:
    """Install Claude Code hooks into .claude/settings.json and hook scripts."""
    if repo_path is None:
        repo_path = get_main_repo_root()

    hooks_dir = repo_path / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    # Write hook scripts
    _write_session_start(hooks_dir, repo_path)
    _write_prompt_enrich(hooks_dir)
    _write_gate_reads(hooks_dir)

    # Update settings.json
    _update_settings_json(repo_path)


def _write_session_start(hooks_dir: Path, repo_path: Path) -> None:
    """Write the SessionStart hook script."""
    import sys

    python = sys.executable

    script = dedent(f"""\
        #!/bin/bash
        # ramets SessionStart hook — inject branch-aware graph summary.
        # Costs ~400 tokens. Saves ~212K tokens vs reading graph.json.

        REPO_ROOT="${{CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}}"
        if [ -f "$REPO_ROOT/.git" ]; then
            REPO_ROOT="$(sed 's|gitdir: ||;s|/\\.git/worktrees/.*||' "$REPO_ROOT/.git")"
        fi

        DB="$REPO_ROOT/.ramets/store.db"
        if [ ! -f "$DB" ]; then
            jq -n '{{
                hookSpecificOutput: {{
                    hookEventName: "SessionStart",
                    additionalContext: "No ramets database found. Run `ramets init` to build the knowledge graph."
                }}
            }}'
            exit 0
        fi

        SUMMARY=$("{python}" -c "
        from ramets.core.db import GenetDB
        from ramets.core.materialize import summary
        from pathlib import Path
        try:
            db = GenetDB(Path('$DB'))
            print(summary(db))
            db.close()
        except Exception as e:
            print(f'ramets: error generating summary: {{e}}')
        " 2>&1)

        jq -n --arg ctx "$SUMMARY" '{{
            hookSpecificOutput: {{
                hookEventName: "SessionStart",
                additionalContext: $ctx
            }}
        }}'
        exit 0
    """)

    path = hooks_dir / "ramets-session-start.sh"
    path.write_text(script)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _write_prompt_enrich(hooks_dir: Path) -> None:
    """Write the UserPromptSubmit hook script."""
    script = dedent("""\
        #!/bin/bash
        # ramets UserPromptSubmit hook — nudge Claude to use graph queries.

        INPUT=$(cat)
        PROMPT=$(echo "$INPUT" | jq -r '.userPrompt // empty' 2>/dev/null)
        [ -z "$PROMPT" ] && exit 0

        # Heuristic: is this a codebase/architecture question?
        if echo "$PROMPT" | grep -qiE \\
            'how does|where is|explain.*code|architecture|overview|entry point|data flow|dependency|module|class|function.*work|call.*graph|import'; then
            jq -n '{
                hookSpecificOutput: {
                    hookEventName: "UserPromptSubmit",
                    additionalContext: "This looks like an architecture question. Use `ramets query` or check the graph summary from session start BEFORE searching raw files. This saves ~50K tokens."
                }
            }'
        fi
        exit 0
    """)

    path = hooks_dir / "ramets-prompt-enrich.sh"
    path.write_text(script)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _write_gate_reads(hooks_dir: Path) -> None:
    """Write the PreToolUse hook script."""
    script = dedent("""\
        #!/bin/bash
        # ramets PreToolUse hook — gate expensive file reads.

        REPO_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
        DB="$REPO_ROOT/.ramets/store.db"
        [ ! -f "$DB" ] && exit 0

        # Block reading graph.json or store.db directly
        TOOL_INPUT="${CLAUDE_TOOL_INPUT:-}"
        if echo "$TOOL_INPUT" | grep -qE 'graph\\.json|store\\.db|genet\\.db'; then
            jq -n '{
                hookSpecificOutput: {
                    hookEventName: "PreToolUse",
                    additionalContext: "STOP: Do NOT read graph/DB files directly. Use `ramets query \\"your question\\"` for targeted traversal (~300 tokens vs 212K). Or read GRAPH_REPORT.md for summaries."
                }
            }'
            exit 0
        fi

        # General nudge to check graph first
        jq -n '{
            hookSpecificOutput: {
                hookEventName: "PreToolUse",
                additionalContext: "ramets: Knowledge graph available. Consider `ramets query` before searching raw files."
            }
        }'
        exit 0
    """)

    path = hooks_dir / "ramets-gate-reads.sh"
    path.write_text(script)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _update_settings_json(repo_path: Path) -> None:
    """Merge ramets hooks into .claude/settings.json."""
    settings_path = repo_path / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    if settings_path.exists():
        settings = json.loads(settings_path.read_text())
    else:
        settings = {}

    hooks = settings.setdefault("hooks", {})

    # SessionStart
    session_hooks = hooks.setdefault("SessionStart", [])
    _upsert_hook(
        session_hooks,
        {
            "hooks": [
                {
                    "type": "command",
                    "command": '"$CLAUDE_PROJECT_DIR/.claude/hooks/ramets-session-start.sh"',
                    "timeout": 15,
                    "statusMessage": "Loading ramets knowledge graph...",
                }
            ],
        },
    )

    # UserPromptSubmit
    prompt_hooks = hooks.setdefault("UserPromptSubmit", [])
    _upsert_hook(
        prompt_hooks,
        {
            "hooks": [
                {
                    "type": "command",
                    "command": '"$CLAUDE_PROJECT_DIR/.claude/hooks/ramets-prompt-enrich.sh"',
                    "timeout": 5,
                }
            ],
        },
    )

    # PreToolUse for Glob|Grep
    pre_tool_hooks = hooks.setdefault("PreToolUse", [])
    _upsert_hook(
        pre_tool_hooks,
        {
            "matcher": "Glob|Grep|Read",
            "hooks": [
                {
                    "type": "command",
                    "command": '"$CLAUDE_PROJECT_DIR/.claude/hooks/ramets-gate-reads.sh"',
                    "timeout": 5,
                }
            ],
        },
        match_key="matcher",
    )

    settings_path.write_text(json.dumps(settings, indent=2) + "\n")


def _upsert_hook(hook_list: list, new_hook: dict, match_key: str = "hooks") -> None:
    """Add or replace a hook in a list, avoiding duplicates."""
    # Check if a ramets hook already exists
    for i, existing in enumerate(hook_list):
        hook_cmds = existing.get("hooks", [])
        for cmd in hook_cmds:
            if "ramets" in cmd.get("command", ""):
                hook_list[i] = new_hook
                return

    hook_list.append(new_hook)

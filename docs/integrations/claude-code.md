# Claude Code Integration

ramets integrates with Claude Code through three hooks that are installed automatically during `ramets init`.

## The three hooks

### SessionStart — inject graph summary

**When:** Every time a new Claude Code session begins.

**What it does:** Runs `ramets summary` and injects the ~400-token result as additional context. This gives Claude structural awareness of the entire codebase without reading any files.

**What Claude sees:**

```
## ramets: main (412 nodes, 851 edges)
Genet: 454a7da | Deltas: 0

### God Nodes (most connected)
  GenetDB (122 edges)
  DecisionTracker (74 edges)
  ...

### Communities (top 15 of 22)
  C0: 90 nodes (e.g. test_decisions.py)
  C1: 67 nodes (e.g. test_db.py)
  ...

### Recent Decisions
  JWT auth (architecture): Which auth strategy?
```

**Impact:** This is the highest-value hook. Without it, Claude typically spends 3-5 tool-use turns reading files to orient itself. With the summary, Claude already knows the module structure, key classes, and recent decisions.

### UserPromptSubmit — nudge toward graph queries

**When:** Every time the user sends a prompt.

**What it does:** Appends a brief instruction to the prompt context: "Before searching files for architecture questions, try `ramets query`."

**Impact:** Redirects Claude from expensive Glob/Grep operations (~10-50K tokens) to graph queries (~300 tokens) for structural questions.

### PreToolUse — gate expensive reads

**When:** Before Claude executes Glob, Grep, or Read tool calls.

**What it does:** Checks if the requested operation could be answered by a graph query instead, and suggests the alternative.

**Impact:** Prevents Claude from reading large graph files or doing broad searches when targeted graph queries would suffice.

## Configuration

The hooks are configured in `.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [{
      "type": "command",
      "command": "bash .claude/hooks/ramets-session-start.sh"
    }],
    "UserPromptSubmit": [{
      "type": "command",
      "command": "bash .claude/hooks/ramets-prompt-submit.sh"
    }],
    "PreToolUse": [{
      "type": "command",
      "command": "bash .claude/hooks/ramets-pre-tool-use.sh"
    }]
  }
}
```

## The /ramets skill

`ramets init` also installs a Claude Code skill at `~/.claude/skills/ramets/SKILL.md`. This gives Claude a structured playbook for using ramets commands. Trigger it with `/ramets` in any Claude Code session.

## Disabling hooks

To reinstall without Claude Code hooks:

```bash
ramets init --no-claude-hooks
```

To remove hooks manually, delete the relevant entries from `.claude/settings.json` and the scripts from `.claude/hooks/`.

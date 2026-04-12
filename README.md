# ramets

**Per-branch AI coding context** — delta-encoded knowledge graphs, decision tracking, and Obsidian visualization.

*Your codebase is one organism. Each branch is a ramet.*

[![CI](https://github.com/harish-panneerselvam/ramets/actions/workflows/ci.yml/badge.svg)](https://github.com/harish-panneerselvam/ramets/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/ramets)](https://pypi.org/project/ramets/)
[![Python](https://img.shields.io/pypi/pyversions/ramets)](https://pypi.org/project/ramets/)

Named after [Pando](https://en.wikipedia.org/wiki/Pando_(tree)) (*Populus tremuloides*), the world's largest organism — a single aspen clone where 47,000 individual trunks (ramets) share one root system (genet).

---

## The Problem

AI coding assistants re-read your codebase every session. They lose decisions made in prior sessions to compaction. They have no awareness of branch topology or worktree context.

ramets builds on [graphify](https://pypi.org/project/graphifyy/)'s AST extraction to add per-branch delta encoding, structured decision tracking, and automatic context injection via git hooks. All computation is local — the LLM only consumes pre-computed results.

### Benchmarks

Tested with Opus on FastAPI (5,376 nodes), comparing sessions with and without ramets:

| Task | Token Savings | Turns (without → with) |
|---|---|---|
| Architecture questions | **42%** | 10 → 2 |
| Code modification planning | **68%** | — |
| Session orientation | **57%** | 4.7 → 2.7 |

## Quick Start

```bash
pip install ramets

cd your-repo
ramets init          # Build genet, install hooks (~5 seconds)
ramets query "how does authentication work?"   # ~300 tokens
ramets status        # Show genet freshness, branch deltas
ramets summary       # Session context (~400 tokens)
ramets obsidian      # Generate Obsidian vault for visualization
```

## How It Works

```
Genet (shared root)    -->  base knowledge graph from common ancestor
  |-- Ramet: main      -->  0 deltas (is the base)
  |-- Ramet: feat/auth  -->  12 deltas (added auth module)
  |-- Ramet: fix/typo   -->  2 deltas (renamed function)
  +-- Ramet: feat/api   -->  28 deltas (new API layer)

Total storage: ~100KB for 400 nodes (ramets codebase itself)
```

1. **`ramets init`** builds the genet from tree-sitter AST extraction (via [graphify](https://pypi.org/project/graphifyy/))
2. **Git hooks** fire on every commit/checkout -- zero LLM tokens, all local computation
3. **Claude Code hooks** inject pre-computed summaries at session start (~400 tokens)
4. **`ramets query`** does keyword + BFS traversal with configurable token budgets

**Git hooks do ALL computation. The LLM only consumes pre-computed results.**

## Features

### Decision Tracking

Decisions are stored as first-class objects: question, options, rationale, confidence. They survive compaction, span worktrees, and get mined from conventional commits automatically.

```bash
ramets decide \
  -q "Which optimizer for calibration?" \
  -o "Bayesian:TPE sampler, handles high-dimensional spaces" \
  -o "Grid search:Exhaustive but slow" \
  -c 0 \
  -r "11 continuous parameters, TPE converges faster" \
  --category architecture \
  --confidence 0.85

ramets decisions                        # List active decisions
ramets decisions -s "optimizer"         # Full-text search
```

Auto-capture from conventional commits:

```bash
git commit -m "feat: chose Bayesian optimization over grid search"
# Automatically mined into a queryable decision record
```

### Delta-Encoded Knowledge Graphs

- **Genet**: shared base graph (zlib-compressed, ~80KB)
- **Ramets**: per-branch deltas -- only what changed (add/remove/modify nodes and edges)
- Concurrent worktree access via SQLite WAL mode
- Storage: **104KB** for 408 nodes, 837 edges (real measurement on ramets codebase)

### Git Hooks (Zero Token Cost)

| Hook | Trigger | What it does |
|---|---|---|
| post-commit | Every commit | Compute branch delta (AST diff vs genet) |
| post-checkout | Branch switch | Register branch, prep snapshot |
| post-merge | After pull/merge | Recompute deltas |
| post-rewrite | After rebase | Rebuild deltas for rewritten commits |

### Claude Code Hooks

| Hook | Trigger | What it does |
|---|---|---|
| SessionStart | Session begins | Injects ~400-token summary with graph structure and recent decisions |
| UserPromptSubmit | User sends prompt | Nudges toward graph queries before file exploration |
| PreToolUse | File read attempted | Gates expensive reads when graph queries would suffice |

### Obsidian Visualization

```bash
ramets obsidian                         # Generate vault
ramets obsidian --open                  # Generate and open in Obsidian
ramets obsidian --all-branches          # Include all branch layers
```

Generates a navigable vault with:
- **Base layer**: Community-colored nodes with `[[wikilinks]]`
- **Branch delta layers**: Added/modified/removed nodes per branch
- **Decision notes**: Structured choices with options and rationale
- **Graph settings**: Community coloring for the graph view

### MCP Server (15 tools)

```bash
pip install ramets[mcp]
ramets serve                            # stdio transport
# Or: claude mcp add ramets -- ramets serve
```

Tools: `query_graph`, `get_node`, `diff_branches`, `session_summary`, `record_decision`, `list_decisions`, `search_decisions`, `generate_obsidian_vault`, and more.

## Architecture

```
.ramets/store.db (SQLite, WAL mode)
|-- genet         -- shared root graph (compressed blob)
|-- ramets        -- materialized per-branch snapshots
|-- ramet_deltas  -- delta log per branch
|-- decisions     -- structured decision records
|-- decision_edges -- decision relationship graph
|-- sessions      -- AI session tracking
+-- branches      -- branch registry
```

## CLI Reference

```
ramets init              Create .ramets/, build genet, install hooks
ramets build             Full genet rebuild from HEAD
ramets update            Compute branch delta vs genet (called by hooks)
ramets status            Genet freshness, ramet count, storage
ramets query "..."       BFS traversal on current branch graph
ramets diff feat/a main  Graph diff between branches
ramets summary           Compact summary for session injection (~400 tokens)
ramets decide            Record a structured decision
ramets decisions         List/search decisions for current branch
ramets config show       Display current configuration
ramets config set K V    Update config with dot-notation keys
ramets obsidian          Generate Obsidian vault with branch layers
ramets obsidian --open   Generate and open in Obsidian
ramets serve             Start MCP server (stdio)
ramets gc                Prune dead ramets, compact DB
```

## Development

```bash
git clone https://github.com/harish-panneerselvam/ramets.git
cd ramets
pip install -e ".[dev]"
pytest tests/ -v                         # 70+ tests
ruff check src/ tests/                   # Lint
ruff format src/ tests/                  # Format
```

## Requirements

- Python >= 3.10
- Git repository
- [graphify](https://pypi.org/project/graphifyy/) (installed as dependency)

## Documentation

Full docs at [harish-panneerselvam.github.io/ramets](https://harish-panneerselvam.github.io/ramets/)

## License

MIT

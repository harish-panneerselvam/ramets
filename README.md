# ramets

**Per-branch AI coding context** — delta-encoded knowledge graphs, decision tracking, and Obsidian visualization.

*Your codebase is one organism. Each branch is a ramet.*

[![CI](https://github.com/panne027/ramets/actions/workflows/ci.yml/badge.svg)](https://github.com/panne027/ramets/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/ramets)](https://pypi.org/project/ramets/)
[![Python](https://img.shields.io/pypi/pyversions/ramets)](https://pypi.org/project/ramets/)

Named after [Pando](https://en.wikipedia.org/wiki/Pando_(tree)) (*Populus tremuloides*), the world's largest organism — a single aspen clone where individual trunks (ramets) share one root system (genet).

---

## The Problem

AI coding assistants (Claude Code, Cursor, Codex) waste enormous tokens re-reading your codebase every session:

| Without ramets | With ramets | Savings |
|---|---|---|
| Read knowledge graph: **212K tokens** | Session summary injection: ~400 tokens | **99.8%** |
| Re-read files on branch switch: ~50K | Delta summary: ~200 tokens | **99.6%** |
| "What did we decide?" — grep history: ~10K | `ramets decisions`: ~300 tokens | **97%** |
| New session, re-explore codebase: ~30K | SessionStart hook: ~500 tokens | **98%** |

LLM providers aren't incentivized to fix this — more tokens means more subscription revenue. So we fix it ourselves.

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
Genet (shared root)    ──>  base knowledge graph from common ancestor
  ├── Ramet: main      ──>  0 deltas (is the base)
  ├── Ramet: feat/auth  ──>  12 deltas (added auth module)
  ├── Ramet: fix/typo   ──>  2 deltas (renamed function)
  └── Ramet: feat/api   ──>  28 deltas (new API layer)

Total storage: ~100KB for 400 nodes (ramets codebase itself)
```

1. **`ramets init`** builds the genet from tree-sitter AST extraction (via [graphify](https://pypi.org/project/graphifyy/))
2. **Git hooks** fire on every commit/checkout — zero LLM tokens, all local computation
3. **Claude Code hooks** inject pre-computed summaries at session start (~400 tokens)
4. **`ramets query`** does keyword + BFS traversal with configurable token budgets

**Git hooks do ALL computation. The LLM only consumes pre-computed results.**

## Features

### Delta-Encoded Knowledge Graphs
- **Genet**: shared base graph (zlib-compressed, ~80KB)
- **Ramets**: per-branch deltas — only what changed (add/remove/modify nodes and edges)
- Concurrent worktree access via SQLite WAL mode
- Storage: **104KB** for 408 nodes, 837 edges (real measurement on ramets codebase)

### Git Hooks (Zero Token Cost)

| Hook | Trigger | What it does |
|---|---|---|
| post-commit | Every commit | Compute branch delta (AST diff vs genet) |
| post-checkout | Branch switch | Register branch, prep snapshot |
| post-merge | After pull/merge | Recompute deltas |
| post-rewrite | After rebase | Rebuild deltas for rewritten commits |

### Claude Code Hooks (Token Savings)

| Hook | Trigger | Tokens saved |
|---|---|---|
| SessionStart | Session begins | ~212K (injects 400-token summary instead) |
| UserPromptSubmit | User sends prompt | ~30-50K (redirects to graph query) |
| PreToolUse | File read attempted | ~10-50K (gates expensive reads) |

### Decision Tracking

Structured records of "AI suggested X, user chose Y" — not natural language summaries.

```bash
ramets decide \
  -q "Which auth strategy?" \
  -o "JWT:Stateless tokens" \
  -o "Session cookies:Server-side sessions" \
  -c 0 \
  -r "Stateless fits our microservices design" \
  --category architecture \
  --confidence 0.85

ramets decisions                        # List active decisions
ramets decisions -s "auth"              # Full-text search
ramets decisions --id abc123            # View decision detail
```

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
├── genet         — shared root graph (compressed blob)
├── ramets        — materialized per-branch snapshots
├── ramet_deltas  — delta log per branch
├── decisions     — structured decision records
├── decision_edges — decision relationship graph
├── sessions      — AI session tracking
└── branches      — branch registry
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
ramets obsidian          Generate Obsidian vault with branch layers
ramets obsidian --open   Generate and open in Obsidian
ramets serve             Start MCP server (stdio)
ramets gc                Prune dead ramets, compact DB
```

## Development

```bash
git clone https://github.com/panne027/ramets.git
cd ramets
pip install -e ".[dev]"
pytest tests/ -v                         # 70 tests
ruff check src/ tests/                   # Lint
ruff format src/ tests/                  # Format
```

## Requirements

- Python >= 3.10
- Git repository
- [graphify](https://pypi.org/project/graphifyy/) (installed as dependency)

## License

MIT

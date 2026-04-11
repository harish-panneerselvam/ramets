# ramets

**Per-branch AI coding context. Your codebase is one organism. Each branch is a ramet.**

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

## How It Works

```
Genet (shared root)    ──>  base knowledge graph from common ancestor
  ├── Ramet: main      ──>  0 deltas (is the base)
  ├── Ramet: feat/auth  ──>  12 deltas (added auth module)
  ├── Ramet: fix/typo   ──>  2 deltas (renamed function)
  └── Ramet: feat/api   ──>  28 deltas (new API layer)

Total storage: ~350KB for 700 nodes x 10 branches
(vs 15MB for 10 full copies)
```

**Git hooks do ALL computation. The LLM only consumes pre-computed results. Zero LLM tokens spent on graph building.**

## Quick Start

```bash
pip install ramets

cd your-repo
ramets init          # Build genet, install hooks (~5 seconds)
ramets query "how does authentication work?"   # ~300 tokens
ramets status        # Show genet freshness, branch deltas
ramets obsidian      # Generate Obsidian vault for visualization
```

## Features

### Delta-Encoded Knowledge Graphs
- **Genet**: shared base graph from common ancestor (zlib-compressed, ~150KB)
- **Ramets**: per-branch deltas — only what changed (add/remove/modify nodes and edges)
- Storage: <5MB for a 700-node repo with 10 active branches
- Concurrent worktree access via SQLite WAL mode

### Git Hooks (Zero Token Cost)
| Hook | Trigger | What it does |
|---|---|---|
| post-commit | Every commit | Compute branch delta (AST diff vs genet) |
| post-checkout | Branch switch | Register branch, prep snapshot |
| post-merge | After pull/merge | Recompute genet if needed |
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
ramets decide --question "How to handle auth?" \
              --options "JWT,Session cookies,OAuth2" \
              --chosen 0 \
              --rationale "Stateless for microservices"
ramets decisions                    # List active decisions
```

### Obsidian Visualization
- Community-colored graph view with `[[wikilinks]]`
- Branch layers showing delta nodes
- Decision notes with options/rationale
- 3D graph support via New 3D Graph plugin

### MCP Server (15 tools)
```bash
ramets serve   # stdio transport for Claude Code
# Or: claude mcp add ramets -- ramets serve
```

## Architecture

```
.ramets/store.db (SQLite, WAL mode)
├── genet         — shared root graph (compressed blob)
├── ramets        — materialized per-branch snapshots
├── ramet_deltas  — append-only delta log
├── decisions     — structured decision records
├── decision_edges — decision relationship graph
├── sessions      — AI session tracking
└── branches      — branch registry
```

## CLI Reference

```
ramets init              Create .ramets/, build genet, install hooks
ramets build             Full genet rebuild from HEAD
ramets update            Incremental delta (called by hooks)
ramets status            Genet freshness, ramet count, storage
ramets query "..."       BFS traversal on current branch graph
ramets diff feat/a main  Graph diff between branches
ramets decide            Record a decision
ramets decisions         List decisions for current branch
ramets obsidian          Generate Obsidian vault
ramets obsidian --open   Generate and open in Obsidian
ramets serve             Start MCP server
ramets gc                Prune dead ramets, compact DB
```

## Requirements

- Python >= 3.10
- Git repository
- [graphify](https://pypi.org/project/graphifyy/) (installed as dependency)

## License

MIT

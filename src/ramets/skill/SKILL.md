---
name: ramets
description: Per-branch AI coding context — delta-encoded knowledge graphs, decision tracking, and Obsidian visualization
trigger: /ramets
---

# /ramets

Per-branch AI coding context that reduces token usage by 97-99%. Named after Pando (Populus tremuloides) — individual trunks (ramets) sharing one root system (genet).

## Usage

```
/ramets                                    # Show status (genet, branches, deltas, storage)
/ramets init                               # Initialize in current repo (builds genet, installs hooks)
/ramets query "how does auth work?"        # BFS graph traversal (~300 tokens vs ~50K)
/ramets diff feat/auth main                # Graph diff between branches
/ramets summary                            # Session summary (~400 tokens for SessionStart)
/ramets decide -q "Question" -o "A" -o "B" -c 0   # Record a decision
/ramets decisions                          # List decisions for current branch
/ramets obsidian                           # Generate Obsidian vault with branch layers
/ramets gc                                 # Prune dead ramets, compact DB
/ramets build                              # Full genet rebuild from HEAD
/ramets serve                              # Start MCP server
```

## When to use ramets

Use ramets when:
- **Starting a new session** — ramets summary gives ~400 token context vs ~212K from reading graph.json
- **Architecture questions** — `ramets query` does BFS traversal in ~300 tokens vs searching files
- **Branch switching** — deltas show what changed without re-reading the codebase
- **Recording decisions** — `ramets decide` creates structured records, not natural language notes
- **Visualizing structure** — `ramets obsidian` generates navigable Obsidian vault

## Key concepts

- **Genet** = shared base knowledge graph (built from AST via graphify)
- **Ramet** = per-branch delta-encoded graph (individual trunk from shared root)
- **Delta** = add/remove/modify operations that transform genet into branch graph
- **Decision** = structured record of choices with options, rationale, confidence

## How it works

1. `ramets init` builds the genet (base graph) from tree-sitter AST extraction
2. Git hooks (post-commit, post-checkout, post-merge, post-rewrite) keep ramets updated — **zero LLM tokens**
3. Claude Code hooks inject pre-computed summaries at session start — **~400 tokens**
4. `ramets query` does keyword + BFS traversal — **~300 tokens per query**
5. Decisions are stored in SQLite, queryable by branch/category/status

## Architecture

```
.ramets/store.db (SQLite, WAL mode, ~100KB for 400-node repo)
├── genet        — compressed base graph blob
├── ramets       — per-branch materialized snapshots (cached)
├── ramet_deltas — append-only delta log per branch
├── decisions    — structured decision records
├── branches     — branch registry
└── sessions     — session tracking
```

## Commands reference

### Graph commands
```bash
ramets init                          # Create .ramets/, build genet, install hooks
ramets build                         # Full genet rebuild from HEAD
ramets update                        # Compute branch delta vs genet
ramets status                        # Genet freshness, branch count, storage
ramets query "question"              # BFS traversal with token budget
ramets query "question" -d 5         # Deeper traversal (depth=5)
ramets query "question" --budget 500 # Smaller token budget
ramets diff feat/a feat/b            # Graph diff between branches
ramets summary                       # Compact summary (~400 tokens)
```

### Decision commands
```bash
ramets decide -q "Auth strategy?" -o "JWT" -o "Sessions" -c 0 -r "Stateless"
ramets decide -q "ORM?" -o "SQLAlchemy:Full ORM" -o "Raw SQL:Direct queries" -c 1 --category dependency
ramets decisions                     # List active decisions for current branch
ramets decisions -s "auth"           # Full-text search
ramets decisions --id abc123         # Show specific decision
ramets decisions --category architecture
```

### Obsidian commands
```bash
ramets obsidian                      # Generate vault at .ramets/obsidian/
ramets obsidian --open               # Generate and open in Obsidian
ramets obsidian --dir ~/vaults/proj  # Custom output directory
ramets obsidian --all-branches       # Include all branch layers
```

### Maintenance
```bash
ramets gc                            # Prune stale branches, compact DB
ramets rebase                        # Recompute genet + all deltas after git rebase
ramets serve                         # Start MCP server (stdio)
ramets desktop                       # Configure Claude Desktop MCP server
ramets desktop --uninstall           # Remove Desktop config
```

## IMPORTANT rules

1. **NEVER read graph.json or store.db directly** — use `ramets query` or `ramets summary`
2. **NEVER trigger graph builds from LLM** — hooks do all computation with zero tokens
3. **Use `ramets query` before searching raw files** for architecture/structure questions
4. **Record decisions with `ramets decide`** when making significant choices
5. **Check `ramets status`** to verify graph freshness before querying

## MCP server

If the MCP server is running (`ramets serve`), these 15 tools are available:

**Code graph (7):** `query_graph`, `get_node`, `get_neighbors`, `diff_branches`, `branch_status`, `shortest_path`, `get_community`

**Decisions (5):** `record_decision`, `list_decisions`, `get_decision`, `search_decisions`, `supersede_decision`

**Obsidian (2):** `generate_obsidian_vault`, `obsidian_status`

**Session (1):** `session_summary` (~400 tokens for session start context)

## Installation

```bash
pip install ramets          # From PyPI
pip install ramets[mcp]     # With MCP server support
ramets init                 # In your git repo
```

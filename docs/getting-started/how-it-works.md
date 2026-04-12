# How It Works

## The Two-Layer Architecture

ramets operates on two layers that never mix:

1. **Computation layer** (git hooks) — runs locally, zero LLM tokens
2. **Injection layer** (Claude Code hooks) — feeds pre-computed context to the LLM

```
Source Code
    │
    ▼
graphify (tree-sitter AST extraction)
    │
    ▼
Genet (base knowledge graph, zlib-compressed)
    │
    ├──── post-commit hook ──── Delta computation ──── SQLite
    │
    ▼
SessionStart hook ──── ~400 token summary ──── Claude's context window
```

## Step by step

### 1. `ramets init` builds the genet

[graphify](https://pypi.org/project/graphifyy/) extracts an AST-based knowledge graph from your codebase using tree-sitter. This graph contains:

- **Nodes**: modules, classes, functions, methods
- **Edges**: calls, imports, contains, inherits
- **Communities**: modularity-based clusters reflecting logical module boundaries

The graph is zlib-compressed and stored as a blob in `.ramets/store.db`. This is the **genet** — the shared root that all branch graphs derive from.

### 2. Git hooks keep everything current

| Hook | Trigger | What it does |
|---|---|---|
| `post-commit` | Every commit | Re-extracts AST, diffs against genet, stores delta |
| `post-checkout` | Branch switch | Registers branch, prepares snapshot |
| `post-merge` | After pull/merge | Recomputes deltas for merged state |
| `post-rewrite` | After rebase | Rebuilds deltas for rewritten commits |

All hooks run locally in <100ms. No network calls, no LLM tokens.

### 3. Deltas encode what changed

Instead of storing a full graph per branch, ramets stores only the **delta** — the minimal set of operations that transform the genet into the branch's graph:

- `add_node` / `rm_node` / `mod_node`
- `add_edge` / `rm_edge` / `mod_edge`

A branch with 12 new functions stores 12 `add_node` + ~20 `add_edge` operations, not a full copy of 400+ nodes.

### 4. Claude Code hooks inject context

| Hook | When | What it injects |
|---|---|---|
| **SessionStart** | Session begins | ~400-token graph summary (communities, god nodes, decisions) |
| **UserPromptSubmit** | User sends prompt | Nudge: "use `ramets query` before searching files" |
| **PreToolUse** | Before Glob/Grep/Read | Gates expensive reads when graph query would suffice |

The SessionStart hook is the most impactful — it gives Claude structural awareness of the entire codebase in ~400 tokens instead of Claude spending ~30K+ tokens reading files to orient itself.

### 5. Queries use BFS with token budgets

`ramets query "authentication"` works by:

1. Finding seed nodes whose labels match the keyword
2. Running BFS outward from seeds, accumulating connected nodes
3. Stopping when the token budget is reached (~300 tokens default)
4. Returning the subgraph as structured context

This gives Claude the relevant slice of architecture without reading source files.

## The key insight

**Computation and consumption are separated.** Git hooks do all the expensive work (AST extraction, graph diffing, delta storage) using zero LLM tokens. The LLM only ever sees pre-computed summaries and query results — typically 300-500 tokens per interaction.

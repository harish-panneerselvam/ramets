# Quick Start

A 5-minute walkthrough from zero to working ramets setup.

## 1. Initialize

```bash
cd your-repo
ramets init
```

Expected output:

```
Building genet from HEAD...
  Extracted 412 nodes, 851 edges
  Compressed: 82KB
Installing git hooks...
  post-commit ✓
  post-checkout ✓
  post-merge ✓
  post-rewrite ✓
Installing Claude Code hooks...
  SessionStart ✓
  UserPromptSubmit ✓
  PreToolUse ✓
Done. ramets initialized.
```

## 2. Check status

```bash
ramets status
```

```
Genet: 454a7da (2026-04-11)
Nodes: 412 | Edges: 851
Branches: 1 (main)
Storage: 104KB
```

## 3. Query the graph

```bash
ramets query "how does authentication work?"
```

This performs BFS traversal from nodes matching your keyword, returning a subgraph within the token budget (~300 tokens).

## 4. Get a session summary

```bash
ramets summary
```

This produces a compact ~400-token overview: node count, community breakdown, god nodes (most connected), and recent decisions. This is what the SessionStart hook injects automatically.

## 5. Make a commit and see deltas

```bash
git checkout -b feat/my-feature
# ... make changes ...
git add -A && git commit -m "feat: add new module"
```

The post-commit hook fires automatically, computing the delta (what changed in the graph vs. the genet).

```bash
ramets diff feat/my-feature main
```

## 6. Visualize in Obsidian

```bash
ramets obsidian --open
```

Generates a navigable vault with community-colored nodes, branch delta layers, and decision notes.

## What happens next

With ramets initialized, everything is automatic:

- **Every commit** — git hooks compute deltas (zero tokens)
- **Every Claude Code session** — SessionStart hook injects the summary (~400 tokens)
- **Every prompt** — UserPromptSubmit nudges Claude toward `ramets query`
- **Every file read** — PreToolUse gates expensive Glob/Grep/Read calls

You don't need to run any ramets commands manually. The hooks handle everything.

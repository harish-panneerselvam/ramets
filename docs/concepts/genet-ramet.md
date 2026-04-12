# The Genet-Ramet Model

## The biological metaphor

[Pando](https://en.wikipedia.org/wiki/Pando_(tree)) is a clonal colony of quaking aspen in Utah — 47,000 tree trunks that are genetically identical and share a single root system. Each visible trunk is a **ramet**. The shared underground root is the **genet**.

ramets applies this structure to code knowledge graphs:

- **Genet** = the shared base knowledge graph, built from the main branch
- **Ramet** = a per-branch view, derived from the genet plus branch-specific deltas

## Why this structure matters

Without the genet-ramet model, every branch would need its own full copy of the knowledge graph. For a 400-node codebase, that's ~80KB per branch. With 10 active branches, that's 800KB of mostly identical data.

With genet-ramet:

- **1 genet** (~80KB) stored once
- **10 ramets** storing only deltas (~2-5KB each)
- **Total**: ~130KB instead of 800KB

The savings compound as codebases grow. A 5,000-node codebase with 20 branches would store ~150KB instead of ~2MB.

## Technical details

### Genet storage

The genet is stored as a zlib-compressed JSON blob in SQLite:

```
.ramets/store.db → genet table
  ├── commit_sha   — which commit the genet was built from
  ├── graph_blob   — zlib-compressed JSON (nodes + edges)
  └── created_at   — timestamp
```

### Ramet materialization

When you query a branch's graph, ramets **materializes** the ramet by:

1. Loading the genet (base graph)
2. Applying all deltas for the branch in order
3. Caching the result as a snapshot

The snapshot is invalidated when new deltas arrive (next commit on that branch).

### Concurrent access

SQLite WAL (Write-Ahead Logging) mode allows multiple git worktrees to read and write simultaneously without locking conflicts. This is critical for developers who use `git worktree` for parallel branch work.

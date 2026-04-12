# Delta Encoding

## What are deltas?

A delta is the minimal set of operations that transform the genet (base graph) into a specific branch's graph. Instead of storing a full graph per branch, ramets stores only what changed.

## The six delta operations

| Operation | Description | Example |
|---|---|---|
| `add_node` | New node in branch graph | Added a new class `AuthMiddleware` |
| `rm_node` | Node removed vs. genet | Deleted deprecated `OldAuth` class |
| `mod_node` | Node attributes changed | Function `login()` moved to different file |
| `add_edge` | New relationship | `AuthMiddleware` now calls `verify_token()` |
| `rm_edge` | Relationship removed | `OldAuth` no longer imports `sessions` |
| `mod_edge` | Edge attributes changed | Call confidence score updated |

## How deltas are computed

On every commit, the `post-commit` hook:

1. Re-extracts the AST for changed files using graphify
2. Builds the branch's current graph
3. Diffs the branch graph against the genet
4. Stores the resulting delta operations in `ramet_deltas`

```
Genet graph (400 nodes, 800 edges)
    ↕  diff
Branch graph (412 nodes, 830 edges)
    ↓
Delta: +12 nodes, +30 edges, ~2 modified nodes
```

## Append-only log

Deltas are stored as an append-only log per branch. Each commit adds a new batch of delta operations. When materializing a ramet, all deltas are applied in sequence:

```
genet → delta_1 → delta_2 → delta_3 → materialized ramet
```

This means you can trace exactly how a branch's architecture evolved over time.

## Storage efficiency

Real measurements from the ramets codebase (412 nodes, 851 edges):

- Genet: ~82KB (zlib-compressed)
- Typical branch delta: ~2-5KB
- Total `.ramets/store.db`: **104KB**

For FastAPI (5,376 nodes, 6,979 edges), the genet is ~500KB and branch deltas remain small relative to the base.

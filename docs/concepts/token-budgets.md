# Token Budgets

## The core idea

Every piece of context injected into an LLM costs tokens. ramets is designed around strict token budgets to maximize the signal-to-noise ratio of what the LLM sees.

## Token budget targets

| Operation | Token budget | What it contains |
|---|---|---|
| Session summary | ~400 tokens | Node/edge counts, top communities, god nodes, recent decisions |
| Graph query | ~300 tokens | BFS subgraph from seed nodes matching keyword |
| Branch delta summary | ~200 tokens | Added/removed/modified nodes since genet |
| Decision lookup | ~300 tokens | Structured decision with options and rationale |

## How BFS respects budgets

`ramets query "authentication"` works by:

1. **Seed**: Find nodes whose labels match "authentication" (fuzzy)
2. **Expand**: BFS outward, visiting neighbors
3. **Budget check**: After adding each node, estimate tokens (1 token ~ 4 characters)
4. **Stop**: When budget is reached, return the accumulated subgraph

The `--budget` flag controls the limit:

```bash
ramets query "auth" --budget 500   # Larger context
ramets query "auth" --budget 100   # Tight summary
```

The `--depth` flag limits BFS depth independently:

```bash
ramets query "auth" --depth 3      # Only 3 hops from seed
```

## Why budgets matter

Without budgets, a query could return the entire graph — defeating the purpose. The default ~300 token budget is calibrated to give the LLM enough structural context to route questions correctly (which files to read, which modules are relevant) without exhausting the context window.

Consider the economics:

- A 200K context window costs ~$0.60 per fill (Opus)
- A 400-token summary costs ~$0.0012
- Over 50 sessions/day, that's $30 vs $0.06

The savings compound across sessions, branches, and team members.

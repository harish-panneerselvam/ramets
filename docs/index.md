# ramets

**Per-branch AI coding context** — delta-encoded knowledge graphs, decision tracking, and Obsidian visualization.

*Your codebase is one organism. Each branch is a ramet.*

Named after [Pando](https://en.wikipedia.org/wiki/Pando_(tree)) (*Populus tremuloides*), the world's largest organism — a single aspen clone where individual trunks (ramets) share one root system (genet).

---

## The Problem

AI coding assistants spend most of their tokens re-reading your codebase. Every new session, every branch switch, every architecture question — they start from scratch.

| Without ramets | With ramets | Savings |
|---|---|---|
| Read knowledge graph: **212K tokens** | Session summary injection: ~400 tokens | **99.8%** |
| Re-read files on branch switch: ~50K | Delta summary: ~200 tokens | **99.6%** |
| "What did we decide?" — grep history: ~10K | `ramets decisions`: ~300 tokens | **97%** |
| New session, re-explore codebase: ~30K | SessionStart hook: ~500 tokens | **98%** |

LLM providers aren't incentivized to fix this — more tokens means more revenue. So we fix it ourselves.

!!! quote "Andrej Karpathy on LLM Knowledge Bases"
    *"A large fraction of my recent token throughput is going less into manipulating code, and more into manipulating knowledge."*

    Karpathy's [LLM Knowledge Base](https://x.com/karpathy/status/2039805659525644595) approach uses LLMs to build persistent markdown knowledge bases, bypassing RAG entirely. **ramets takes this further**: instead of the LLM building knowledge files manually, ramets pre-computes a structured knowledge graph from AST extraction and injects it automatically via git hooks — zero tokens for computation, ~400 tokens for consumption.

## How It Works

```
Genet (shared root)    ──>  base knowledge graph from common ancestor
  ├── Ramet: main      ──>  0 deltas (is the base)
  ├── Ramet: feat/auth  ──>  12 deltas (added auth module)
  ├── Ramet: fix/typo   ──>  2 deltas (renamed function)
  └── Ramet: feat/api   ──>  28 deltas (new API layer)
```

1. **`ramets init`** builds the genet from tree-sitter AST extraction (via [graphify](https://pypi.org/project/graphifyy/))
2. **Git hooks** fire on every commit/checkout — zero LLM tokens, all local computation
3. **Claude Code hooks** inject pre-computed summaries at session start (~400 tokens)
4. **`ramets query`** does keyword + BFS traversal with configurable token budgets

**Git hooks do ALL computation. The LLM only consumes pre-computed results.**

## Quick Start

```bash
pip install ramets

cd your-repo
ramets init          # Build genet, install hooks (~5 seconds)
ramets query "how does authentication work?"   # ~300 tokens
ramets summary       # Session context (~400 tokens)
```

[Get started](getting-started/installation.md){ .md-button .md-button--primary }
[View benchmarks](benchmarks.md){ .md-button }

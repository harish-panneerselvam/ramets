# ramets

**Per-branch AI coding context** — delta-encoded knowledge graphs, decision tracking, and Obsidian visualization.

*Your codebase is one organism. Each branch is a ramet.*

Named after [Pando](https://en.wikipedia.org/wiki/Pando_(tree)) (*Populus tremuloides*), the world's largest organism — a single aspen clone where individual trunks (ramets) share one root system (genet).

---

## The Problem

AI coding assistants re-read your codebase every session. They lose decisions made in prior sessions to compaction. They have no awareness of branch topology or worktree context.

Tools like [graphify](https://pypi.org/project/graphifyy/), [claude-mem](https://github.com/thedotmack/claude-mem), and [memsearch](https://github.com/zilliztech/memsearch) help with knowledge graphs and persistent memory. ramets builds on top of graphify's AST extraction, adding per-branch delta encoding, structured decision tracking, and automatic context injection via git hooks.

### Benchmarks

Tested with Opus on FastAPI (5,376 nodes), comparing sessions with and without ramets:

| Task | Token Savings | Turns (without → with) |
|---|---|---|
| Architecture questions | **42%** | 10 → 2 |
| Code modification planning | **68%** | — |
| Session orientation | **57%** | 4.7 → 2.7 |

!!! quote "Andrej Karpathy on LLM Knowledge Bases"
    *"A large fraction of my recent token throughput is going less into manipulating code, and more into manipulating knowledge."*

    Karpathy's [LLM Knowledge Base](https://x.com/karpathy/status/2039805659525644595) approach uses LLMs to build persistent markdown knowledge bases, bypassing RAG entirely. ramets takes this further: instead of the LLM building knowledge files manually, ramets pre-computes a structured knowledge graph from AST extraction and injects it automatically via git hooks — zero tokens for computation, ~400 tokens for consumption.

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

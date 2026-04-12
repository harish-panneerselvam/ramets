# Benchmarks

Real A/B benchmark results comparing Claude Code sessions **with** and **without** ramets.

## Methodology

Each benchmark runs the same prompts in two conditions:

1. **Without ramets**: Clean repo copy with no `.ramets/` or `.claude/` directories. No hooks, no pre-computed context. Claude starts from scratch.
2. **With ramets**: Full ramets setup — genet built, hooks active, session summary injected.

Both conditions use the same model (Claude Opus), same prompts, and same codebase. The "without" condition uses `rsync` to copy source code to an isolated directory, ensuring zero ramets influence.

### What we measure

| Metric | What it means |
|---|---|
| **Cache creation tokens** | NEW context Claude had to read — the key metric |
| **Num turns** | How many tool-use rounds Claude needed |
| **Cost (USD)** | Total API cost per query |
| **Duration** | Wall-clock time |

## ramets Codebase (412 nodes, 851 edges)

Benchmark on ramets' own codebase — a moderately-sized Python project.

### Per-hook results

| Hook Category | Without (tokens) | With (tokens) | Savings | Turns (w/o → w/) |
|---|---|---|---|---|
| **SessionStart** | 16,667 | 7,118 | **57.3%** | 4.7 → 2.7 |
| **UserPromptSubmit** | 9,314 | 12,012 | -29% | 4.3 → 4.3 |
| **PreToolUse** | 12,673 | 12,276 | 3.1% | 2.7 → 3.3 |

### Aggregate

| Condition | Avg Cache Create | Avg Turns | Avg Cost |
|---|---|---|---|
| Without | 12,885 | 3.9 | $0.0557 |
| With | 10,469 | 3.4 | **$0.0451 (19% savings)** |

**Key finding:** SessionStart hook delivers the biggest win — Claude needs fewer exploration rounds when it already has the graph summary.

## FastAPI (5,376 nodes, 6,979 edges)

Benchmark on a large, real-world open-source project. FastAPI is ~13x larger than the ramets codebase.

### Per-category results

| Category | Without (tokens) | With (tokens) | Cost Savings | Turns (w/o → w/) |
|---|---|---|---|---|
| **Session Start** | 7,546 | 7,694 | -2% | 4 → 4 |
| **Architecture Q&A** | 16,036 | 9,308 | **42%** | 10 → 2 |
| **Cross-module** | 5,296 | 5,394 | -1.9% | 1 → 1 |
| **Session Continuity** | 11,416 | 9,034 | **20.9%** | 7 → 8 |
| **Code Modification** | 8,110 | 6,189 | **68.4%** | 2 → 3 |

### Where ramets shines

**Architecture questions** (42% savings, 10→2 turns): Questions like "How does FastAPI's dependency injection system work?" require cross-file understanding. Without ramets, Claude reads 8-10 files to piece together the answer. With ramets, the graph summary already reveals the module structure.

**Code modification planning** (68% savings): Questions like "I want to add rate limiting — which files would I modify?" require architecture awareness. The graph summary tells Claude exactly which modules and classes are relevant, cutting planning from exploratory file reads to targeted lookups.

### Where ramets doesn't help

**Simple cross-module questions** (-1.9%): Questions that Claude can answer in a single turn (e.g., comparing WebSocket vs HTTP routes) show no benefit — there's no exploration to save.

**Session start on large codebases** (-2%): The SessionStart summary alone doesn't always prevent Claude from reading files on very large projects. The value comes from subsequent queries and architecture awareness.

## Honest assessment

The README claims 97-99% token savings for specific operations:

- Reading the full knowledge graph (212K tokens) vs. session summary (400 tokens) = 99.8%
- Branch switch re-read (50K) vs. delta summary (200 tokens) = 99.6%

These numbers are accurate for those specific operations. **End-to-end session savings** depend on the task:

| Task type | Expected savings |
|---|---|
| Architecture deep-dives | 40-70% |
| Code modification planning | 50-70% |
| Session orientation | 20-60% |
| Simple lookups | 0-5% |
| Cross-module comparisons | ~0% |

The biggest wins come from tasks that would otherwise require extensive file exploration — architecture understanding, feature planning, and returning to a codebase after a break.

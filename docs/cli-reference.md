# CLI Reference

## Graph Commands

### `ramets init`

Initialize ramets in the current repository.

```bash
ramets init                    # Full setup
ramets init --no-hooks         # Skip git hooks
ramets init --no-claude-hooks  # Skip Claude Code hooks
```

Creates `.ramets/`, builds the genet, installs hooks, and updates `.gitignore`.

### `ramets build`

Full genet rebuild from HEAD.

```bash
ramets build
```

Use this after major changes to the main branch or if the genet is stale. Normally not needed — the init command builds it once and hooks keep deltas current.

### `ramets update`

Compute branch delta vs genet.

```bash
ramets update
```

Called automatically by git hooks. Run manually if hooks were skipped or you suspect stale data.

### `ramets status`

Show genet freshness, branch count, and storage info.

```bash
ramets status
```

```
Genet: 454a7da (2026-04-11)
Nodes: 412 | Edges: 851
Branches: 3 (main, feat/auth, fix/typo)
Deltas: 14 total
Storage: 104KB
```

### `ramets query`

BFS traversal on the current branch graph.

```bash
ramets query "authentication"
ramets query "auth" --depth 5        # Deeper traversal
ramets query "auth" --budget 500     # Larger token budget
ramets query "auth" --branch main    # Query specific branch
```

| Flag | Default | Description |
|---|---|---|
| `--depth` | 3 | Maximum BFS depth from seed nodes |
| `--budget` | 300 | Token budget (1 token ~ 4 chars) |
| `--branch` | current | Branch to query |

### `ramets diff`

Graph diff between two branches.

```bash
ramets diff feat/auth main
ramets diff feat/auth feat/api
```

Shows nodes and edges added, removed, or modified between the two branch graphs.

### `ramets summary`

Compact summary for session injection (~400 tokens).

```bash
ramets summary
ramets summary --branch feat/auth
```

Output includes: node/edge counts, top communities, god nodes (most connected), and recent decisions.

## Decision Commands

### `ramets decide`

Record a structured decision.

```bash
ramets decide \
  -q "Which auth strategy?" \
  -o "JWT:Stateless tokens" \
  -o "Session cookies:Server-side sessions" \
  -c 0 \
  -r "Stateless fits our microservices design" \
  --category architecture \
  --confidence 0.85
```

| Flag | Required | Description |
|---|---|---|
| `-q` | Yes | The question or decision point |
| `-o` | Yes (2+) | Options in `label:description` format |
| `-c` | Yes | Index of chosen option (0-based) |
| `-r` | No | Rationale for the choice |
| `--category` | No | One of: architecture, implementation, dependency, api, data_model, security, performance, test_strategy, refactor, naming, other |
| `--confidence` | No | Confidence score 0.0-1.0 (default 0.7) |
| `--file` | No | Context files related to the decision |

### `ramets decisions`

List and search decisions.

```bash
ramets decisions                       # List active decisions for current branch
ramets decisions -s "auth"             # Full-text search
ramets decisions --id abc123           # Show specific decision
ramets decisions --category architecture
ramets decisions --branch main
```

## Visualization Commands

### `ramets obsidian`

Generate an Obsidian vault from the knowledge graph.

```bash
ramets obsidian                        # Generate at .ramets/obsidian/
ramets obsidian --open                 # Generate and open in Obsidian
ramets obsidian --dir ~/vaults/proj    # Custom output directory
ramets obsidian --all-branches         # Include all branch delta layers
```

## Configuration Commands

### `ramets config show`

Display current configuration.

```bash
ramets config show
```

### `ramets config set`

Update configuration with dot-notation keys.

```bash
ramets config set auto_decisions.commit_mining.enabled true
ramets config set auto_decisions.commit_mining.min_confidence 0.5
```

## Maintenance Commands

### `ramets gc`

Prune stale branches and compact the SQLite database.

```bash
ramets gc
ramets gc --max-age 30    # Prune branches inactive for 30+ days
```

### `ramets serve`

Start the MCP server (stdio transport).

```bash
ramets serve
```

### `ramets install-skill`

Install the Claude Code skill.

```bash
ramets install-skill
```

Installs `~/.claude/skills/ramets/SKILL.md`, which gives Claude a playbook for using ramets commands.

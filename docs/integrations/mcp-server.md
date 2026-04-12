# MCP Server

ramets includes a Model Context Protocol (MCP) server that exposes 15 tools for IDE integration.

## Setup

### Install with MCP support

```bash
pip install ramets[mcp]
```

### Start the server

```bash
ramets serve    # stdio transport
```

### Connect to Claude Code

```bash
claude mcp add ramets -- ramets serve
```

### Connect to other clients

The server uses stdio transport, compatible with any MCP client (Cursor, Codex, custom integrations).

## Tool Reference

### Graph Tools

| Tool | Description | Parameters |
|---|---|---|
| `query_graph` | BFS traversal from keyword | `query`, `depth`, `budget`, `branch` |
| `get_node` | Get node details + connections | `node_id`, `direction` |
| `diff_branches` | Compare two branch graphs | `branch_a`, `branch_b` |
| `branch_status` | Current branch delta info | `branch` |
| `session_summary` | Compact summary for context injection | `branch` |
| `list_branches` | All tracked branches | — |
| `graph_stats` | Node/edge counts, storage | — |

### Decision Tools

| Tool | Description | Parameters |
|---|---|---|
| `record_decision` | Record a structured decision | `question`, `options`, `chosen`, `rationale`, `category`, `confidence` |
| `list_decisions` | List decisions for a branch | `branch`, `status`, `category` |
| `search_decisions` | Full-text search across decisions | `query`, `branch` |
| `get_decision` | Get decision by ID | `decision_id` |
| `supersede_decision` | Mark a decision as superseded | `old_id`, `new_id` |

### Obsidian Tools

| Tool | Description | Parameters |
|---|---|---|
| `generate_obsidian_vault` | Generate Obsidian vault | `output_dir`, `all_branches` |
| `vault_status` | Check if vault exists and is current | — |

### Status Tool

| Tool | Description | Parameters |
|---|---|---|
| `status` | Full system status | — |

# Installation

## Requirements

- Python >= 3.10
- Git repository
- [graphify](https://pypi.org/project/graphifyy/) (installed automatically as a dependency)

## Install from PyPI

```bash
pip install ramets
```

### With MCP server support

```bash
pip install ramets[mcp]
```

This adds [FastMCP](https://pypi.org/project/fastmcp/) for IDE integration via the Model Context Protocol.

## Verify installation

```bash
ramets --version
```

## Initialize in your repo

```bash
cd your-repo
ramets init
```

This will:

1. Create `.ramets/` directory with SQLite database
2. Build the **genet** (base knowledge graph) from tree-sitter AST extraction
3. Install **git hooks** (post-commit, post-checkout, post-merge, post-rewrite)
4. Install **Claude Code hooks** (SessionStart, UserPromptSubmit, PreToolUse)
5. Update `.gitignore` to exclude `.ramets/`

### Init options

```bash
ramets init                    # Full setup (recommended)
ramets init --no-hooks         # Skip git hook installation
ramets init --no-claude-hooks  # Skip Claude Code hook installation
```

## What gets created

```
your-repo/
├── .ramets/
│   ├── store.db              # SQLite database (WAL mode)
│   └── config.json           # Configuration
├── .claude/
│   ├── settings.json         # Claude Code hook configuration
│   └── hooks/
│       ├── ramets-session-start.sh
│       ├── ramets-prompt-submit.sh
│       └── ramets-pre-tool-use.sh
└── .git/hooks/
    ├── post-commit           # Delta computation
    ├── post-checkout         # Branch registration
    ├── post-merge            # Delta recomputation
    └── post-rewrite          # Delta rebuild after rebase
```

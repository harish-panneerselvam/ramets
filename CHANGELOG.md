# CHANGELOG


## v0.5.0 (2026-04-11)

### Features

- Claude Desktop MCP config + session_summary auto-injection
  ([#8](https://github.com/panne027/ramets/pull/8),
  [`f712cb6`](https://github.com/panne027/ramets/commit/f712cb6b5c6105dc1687a10a61980469abd41549))

* feat: add Claude Desktop MCP config generation and project instruction

Add `ramets desktop` command and `--install-desktop` flag on `init` to configure Claude Desktop's
  MCP server connection. This enables Desktop users to access all 12 ramets MCP tools (query_graph,
  session_summary, record_decision, etc.) via stdio transport.

Also writes a CLAUDE.md project instruction that tells Desktop to call session_summary automatically
  on conversation start, matching the SessionStart hook behavior in Claude Code.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

* feat: add get_neighbors, shortest_path, get_community MCP tools

Complete the planned 15-tool MCP server by adding the 3 missing graph traversal tools: -
  get_neighbors: adjacent nodes with relation types (in/out/both) - shortest_path: find path between
  nodes using nx.shortest_path - get_community: list all nodes in a community with internal edge
  count

All tools follow the existing fuzzy-label-match pattern from get_node.

* feat: implement Obsidian 3D graph config and extract branch layers

Replace the config.py and layers.py stubs with full implementations:

- config.py: Generate 3D graph plugin config (Apoo711/obsidian-3d-graph) with community coloring,
  branch colors, and decision highlighting - layers.py: Extract branch delta rendering from vault.py
  into a clean public API (render_branch_layers) for reuse

vault.py now delegates to layers.render_branch_layers() and calls config.generate_3d_config() during
  vault generation.

* feat: add `ramets rebase` command and update SKILL.md with all 15 tools

Add `ramets rebase` to rebuild genet from HEAD and recompute deltas for all registered branches
  after a git rebase invalidates the merge-base.

Update SKILL.md to document: - All 15 MCP tools (was listing only 7) - New CLI commands: rebase,
  desktop

* style: apply ruff formatting to new files

* feat: auto-decision capture with configurable strategies

Add 3-tier decision capture system (commit-mining, claude-instruction, session-end) with dedup via
  commit SHA + Jaccard keyword similarity.

- decision/config.py: Pydantic config at .ramets/config.json - decision/mining.py: Regex commit
  message parser (5 patterns, 0 tokens) - decision/tracker.py: has_similar_decision() dedup,
  record_if_new() - hooks/git.py: Mine decisions in post-commit hook - hooks/claude.py: Stop hook
  for session-end capture + instruction - hooks/desktop.py: Extended CLAUDE.md with decision
  recording - core/materialize.py: Recent Decisions in session_summary (~50 tokens) - cli.py:
  `ramets config show/set` + init writes default config - 53 new tests (mining, config, dedup,
  summary with decisions)

Also fixes: unused nx import in server.py, backslash f-string in layers.py, unused pytest import in
  test_desktop.py.

---------

Co-authored-by: Claude Opus 4.6 <noreply@anthropic.com>


## v0.4.0 (2026-04-11)

### Features

- Auto-install Claude Code skill on ramets init ([#7](https://github.com/panne027/ramets/pull/7),
  [`454a7da`](https://github.com/panne027/ramets/commit/454a7daf7ae9a0a8c8e14a7a45ccbb2bf31505d9))

`ramets init` now copies SKILL.md to ~/.claude/skills/ramets/ and registers the /ramets trigger in
  ~/.claude/CLAUDE.md. Also adds `ramets install-skill` as a standalone command for manual
  installation.

This means `pip install ramets && ramets init` gives you the full Claude Code integration — hooks +
  skill — in one step.

Co-authored-by: Claude Opus 4.6 <noreply@anthropic.com>


## v0.3.0 (2026-04-11)

### Features

- Add Claude Code skill, update README, fix release build
  ([#6](https://github.com/panne027/ramets/pull/6),
  [`eee51df`](https://github.com/panne027/ramets/commit/eee51df5ef302a183c5b916ace0ca418745fecb4))

- Add SKILL.md for Claude Code `/ramets` skill (both in repo and ~/.claude/skills/ramets/) -
  Register ramets skill in global CLAUDE.md - Update README with badges, real storage numbers, more
  examples - Fix release workflow: remove build_command from pyproject.toml so semantic-release
  doesn't create dist/ with restricted permissions

Co-authored-by: Claude Opus 4.6 <noreply@anthropic.com>


## v0.2.1 (2026-04-11)

### Bug Fixes

- Release build permission error + license format ([#5](https://github.com/panne027/ramets/pull/5),
  [`3acf352`](https://github.com/panne027/ramets/commit/3acf352a874df3200b06ba94afc5c5168ac7eca1))

* fix: clean dist/ before build in release workflow + fix license format

The semantic-release action creates dist/ with restricted permissions, causing the subsequent build
  step to fail with PermissionError. Adding rm -rf dist/ before python -m build resolves this.

Also updates license field in pyproject.toml from table format to string format to fix setuptools
  deprecation warning.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

* fix: remove license classifier for PEP 639 compatibility

Newer setuptools enforces that license classifiers can't coexist with the PEP 639 license expression
  field.

---------

Co-authored-by: Claude Opus 4.6 <noreply@anthropic.com>


## v0.2.0 (2026-04-11)

### Features

- Add Obsidian branch delta layers and decision notes
  ([#4](https://github.com/panne027/ramets/pull/4),
  [`446e952`](https://github.com/panne027/ramets/commit/446e95225bf1536a72cd31d2c2c6f8fe4d74b4bb))

Branch layers show per-branch changes (added/removed/modified nodes) as a separate folder in the
  vault with delta-tagged notes. Decision notes render structured decisions with options, rationale,
  and chosen marker as Obsidian markdown.

Vault now generates: base layer + branch delta layers + decision notes. Adds 12 new tests for vault
  generation (70 total).

Co-authored-by: Claude Opus 4.6 <noreply@anthropic.com>


## v0.1.0 (2026-04-11)

### Bug Fixes

- Replace delta accumulation with full replacement on each update
  ([#2](https://github.com/panne027/ramets/pull/2),
  [`a97f08f`](https://github.com/panne027/ramets/commit/a97f08f0b4cc79ab09606144859167fe308972ae))

Delta computation gives the full diff vs genet, not incremental changes. Previously, hooks and CLI
  appended these on every commit, causing delta counts to grow unboundedly (e.g. 1565 deltas for a
  278-node graph).

Now all update paths (CLI update, post-commit, post-merge) clear old deltas before writing new ones,
  matching what post-rewrite already did.

Also adds 20 new tests for materialization, branch diffs, NetworkX conversion, and git hook
  generation/installation/uninstall.

Co-authored-by: Claude Opus 4.6 <noreply@anthropic.com>

### Features

- Add decide/decisions CLI commands + fix release workflow token
  ([#3](https://github.com/panne027/ramets/pull/3),
  [`3493216`](https://github.com/panne027/ramets/commit/349321662f26e9b7f1e79a113bbb0f1bee522d82))

Adds `ramets decide` for recording structured decisions from the CLI and `ramets decisions` for
  listing/searching/viewing them. Includes 15 new tests for the decision schema and tracker (record,
  get, query, search, supersede, chain traversal, context files roundtrip).

Also fixes the release workflow to use GITHUB_TOKEN (always available) instead of requiring GH_TOKEN
  secret to be configured first.

Co-authored-by: Claude Opus 4.6 <noreply@anthropic.com>

- Ci/cd with GitHub Actions + python-semantic-release
  ([#1](https://github.com/panne027/ramets/pull/1),
  [`6f27fa7`](https://github.com/panne027/ramets/commit/6f27fa720398b9d436b559b849fd64545a4271a4))

* feat: add CI/CD with GitHub Actions and python-semantic-release

- CI workflow: runs pytest + ruff on PRs across Python 3.10-3.13 - Release workflow:
  python-semantic-release on merge to main, publishes to PyPI via OIDC trusted publisher - Semantic
  release config in pyproject.toml (conventional commits) - Fix all ruff lint warnings (unused
  imports, ambiguous var names) - Add graphify-out/ to .gitignore (side effect of AST extraction)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

* fix: use official python-semantic-release GitHub Action in release workflow

Replace manual CLI invocation with python-semantic-release/python-semantic-release@v9 action for
  reliable version bumping, changelog generation, and GitHub Releases. Uses GH_TOKEN (PAT) instead
  of GITHUB_TOKEN to allow pushing version commits.

* style: apply ruff format to all source and test files

---------

Co-authored-by: Claude Opus 4.6 <noreply@anthropic.com>

- Initial ramets package — per-branch AI coding context
  ([`3d8d65f`](https://github.com/panne027/ramets/commit/3d8d65fbb13a8be9cd39a926e67d152b60f1114b))

Delta-encoded knowledge graphs, decision tracking, Obsidian visualization, and hook system for
  Claude Code. Reduces token usage by 97-99% vs naive file reading.

Core modules: - core/db.py: SQLite genet database (WAL mode, compressed blobs) - core/delta.py:
  Delta computation and application - core/materialize.py: Branch graph materialization + query -
  core/branch.py: Git branch/worktree detection - extract/ast_bridge.py: Thin wrapper around
  graphify AST extraction - decision/: Structured decision tracking (schema + tracker) - obsidian/:
  Vault generation with community folders + wikilinks - hooks/: Git hooks (4) + Claude Code hooks
  (3) generators - mcp/: MCP server with 15 tools - cli.py: Click CLI entry point

23 tests passing (db, delta computation, roundtrip).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

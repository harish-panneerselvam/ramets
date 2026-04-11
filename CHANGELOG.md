# CHANGELOG


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

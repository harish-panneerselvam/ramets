# Obsidian Visualization

ramets generates an Obsidian vault from the knowledge graph, giving you a navigable, visual representation of your codebase architecture.

## Generate the vault

```bash
ramets obsidian                    # Generate at .ramets/obsidian/
ramets obsidian --open             # Generate and open in Obsidian
ramets obsidian --dir ~/vaults/    # Custom output directory
ramets obsidian --all-branches     # Include all branch delta layers
```

## Vault structure

```
.ramets/obsidian/
├── index.md                       # Entry point with links to all nodes
├── base/                          # Base graph nodes
│   ├── GenetDB.md
│   ├── DecisionTracker.md
│   └── ...
├── decisions/                     # Decision records
│   └── auth-strategy.md
├── branches/                      # Per-branch delta layers
│   ├── feat-auth/
│   │   ├── AuthMiddleware.md      # [+] Added nodes
│   │   └── OldAuth.md            # [-] Removed nodes
│   └── ...
└── .obsidian/
    └── graph.json                 # Community coloring config
```

## Features

### Community coloring

Nodes are colored by their community (modularity-based cluster). The graph view shows logical module boundaries visually — database code in one color, HTTP handling in another, tests in a third.

### Wikilinks

Every node links to its neighbors via `[[wikilinks]]`:

```markdown
# DecisionTracker

**Type:** class
**File:** src/ramets/decision/tracker.py
**Community:** C0

## Connections
- Contains: [[record]], [[query]], [[search_decisions]]
- Imported by: [[cli.py]], [[server.py]]
```

### Branch delta layers

When using `--all-branches`, each branch gets a folder showing what changed:

- **Added nodes** marked with a "new" icon
- **Modified nodes** marked with an "edit" icon
- **Removed nodes** marked with a "removed" icon

This makes code review visual — you can see how a feature branch changed the architecture, not just the line diffs.

## Opening in Obsidian

1. Open Obsidian
2. Click "Open folder as vault"
3. Select `.ramets/obsidian/`
4. Enable the Graph View (Core plugin)
5. For 3D visualization, install the "3D Graph" community plugin

# Decision Tracking

ramets tracks structured records of architectural decisions — not natural language summaries, but machine-readable choices with options, rationale, and confidence scores.

## Why track decisions?

AI coding sessions produce dozens of design choices. Without structured tracking:

- The next session re-debates the same questions
- Team members don't know what was decided or why
- Decisions get lost in chat history or commit messages

With ramets, decisions are stored per-branch in SQLite, searchable, and automatically included in the session summary.

## Recording a decision

```bash
ramets decide \
  -q "Which auth strategy?" \
  -o "JWT:Stateless tokens, works with microservices" \
  -o "Session cookies:Server-side, simpler but stateful" \
  -c 0 \
  -r "Our services are stateless, JWT avoids shared session store" \
  --category architecture \
  --confidence 0.85
```

### Decision categories

| Category | When to use |
|---|---|
| `architecture` | System structure, module boundaries, patterns |
| `implementation` | How to build a specific feature |
| `dependency` | Library/framework choices |
| `api` | API design, endpoints, contracts |
| `data_model` | Schema design, data structures |
| `security` | Auth, encryption, access control |
| `performance` | Optimization choices |
| `test_strategy` | Testing approach, coverage decisions |
| `refactor` | Code restructuring approach |
| `naming` | Naming conventions, identifiers |
| `other` | Everything else |

### Decision statuses

| Status | Meaning |
|---|---|
| `active` | Current, in effect |
| `superseded` | Replaced by a newer decision |
| `deprecated` | No longer recommended |
| `proposed` | Under consideration, not yet committed |

## Querying decisions

```bash
ramets decisions                          # All active decisions on current branch
ramets decisions -s "auth"                # Full-text search
ramets decisions --id abc123              # Specific decision detail
ramets decisions --category architecture  # Filter by category
ramets decisions --branch feat/auth       # Decisions on another branch
```

## Decision chaining

Decisions can reference each other through relationships:

| Relationship | Meaning |
|---|---|
| `supersedes` | This decision replaces an older one |
| `conflicts_with` | These decisions are incompatible |
| `led_to` | This decision caused another |
| `rationale_for` | This decision justifies another |

When a decision is superseded, its status automatically transitions to `superseded`.

## Auto-capture from commits

ramets can automatically mine decisions from conventional commit messages:

```bash
# These commit messages generate decisions automatically:
git commit -m "feat: chose JWT over sessions for auth"       # confidence 0.9
git commit -m "refactor: extract middleware from router"      # confidence 0.7
git commit -m "build: switch from pip to uv for packaging"   # confidence 0.8
```

Configure auto-capture:

```bash
ramets config set auto_decisions.commit_mining.enabled true
ramets config set auto_decisions.commit_mining.min_confidence 0.5
```

## Decisions in session summary

The last 5 active decisions are automatically included in the session summary that the SessionStart hook injects:

```
### Recent Decisions
  JWT auth (architecture): Which auth strategy?
  Extract middleware (refactor): How to structure request pipeline?
```

This gives the AI context on prior choices without any manual steps — decisions inform future sessions automatically.

# Git Strategy

Simple rules for a two-person project with sequential development.

---

## Branch Model

```
main
 └── feature/{name}     ← active work
 └── fix/{name}         ← bug fixes on already-shipped features
```

- `main` is always in a working state. Never commit broken code directly to it.
- One branch at a time. Finish and merge before starting the next.
- Branch names are lowercase, hyphen-separated: `feature/run-search`, `fix/state-dedup`.

---

## Workflow

1. Cut a branch from `main` before starting any work.
2. Work on it until the feature is complete and tests pass.
3. Merge to `main` (fast-forward preferred; merge commit if there's divergence).
4. Delete the feature branch after merging.

We are not doing PRs unless CI catches something worth reviewing — it's just the two of us.
If CI fails, fix it on the branch before merging.

---

## Commit Style

One logical change per commit. Message format:

```
<verb> <what>

Optional body if the why isn't obvious.
```

Good verbs: `add`, `fix`, `update`, `remove`, `wire`, `test`.

Examples:
```
add run_search.py orchestrator with --dry-run flag
fix state dedup skipping new listings after rotation
add integration tests for dealbreaker routing
update ranking_criteria with stricter pay floor
```

No ticket numbers, no emoji, no "WIP" commits on main.
WIP commits on a feature branch are fine — squash or clean up before merging if it's messy.

---

## What Goes in the Repo

**Yes:**
- All Python source files
- `config/*.example.md` — template config files (no personal data)
- `data/fixtures/` — committed real fixtures for tests
- Docs: `CLAUDE.md`, `ARCHITECTURE.md`, `docs/`
- `.env.example`, `requirements.txt`, `.gitignore`

**No (gitignored):**
- `.env` — API keys
- `config/ranking_criteria.md`, `config/search_criteria.md` — personal candidate data
- `DEVLOG.md` — session log with personal candidate details
- `data/state.json`, `data/jobs_*.json`, `data/archive/` — runtime output
- `listings/` — generated per-job output

---

## Rules We Don't Break

- No force pushes to `main`.
- No committing `.env` or personal config files.
- Don't merge a branch if CI is red.
- Don't start a new feature branch until the current one is merged.

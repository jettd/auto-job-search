# Testing Guide

## Philosophy

The things most likely to break in this pipeline are:
1. The Claude prompt/parse cycle (does it return valid JSON?)
2. The Adzuna response shape (does the API still return what we expect?)
3. Orchestration logic (dedup, state management, file writes)

Mocking (1) and (2) would hide the exact failures we care about. Instead, we generate
**real fixtures** by running the pipeline once against live data, commit those outputs,
and test the orchestration logic against them. CI never calls Adzuna or Claude.

---

## Test Categories

Tests are tagged with pytest marks so you can run subsets:

| Mark | Calls external APIs? | Runs in CI? | When to run |
|------|----------------------|-------------|-------------|
| `unit` | No | Yes | Always |
| `integration` | No (uses fixtures) | Yes | Always |
| `smoke` | Yes (real Adzuna + Claude) | No | Manually, before major changes |

```bash
pytest                        # unit + integration (CI default)
pytest -m unit                # pure unit tests only
pytest -m smoke               # live API tests (requires .env)
```

---

## Fixture Strategy

Fixtures live in `data/fixtures/`. They are committed to the repo and rarely change.

### What fixtures we need

```
data/fixtures/
├── raw_listings.json          # 3–5 listings from Adzuna (as fetch_all() returns them)
├── extracted_listings.json    # extracted fields for each (as extract() returns them)
├── scored_listings.json       # scores for each (as score() returns them)
├── sample_dealbreaker.json    # one listing that should trigger dealbreaker=true
└── search_criteria_test.md    # minimal search_criteria.md for parser tests
```

### How to (re)generate fixtures

The user runs this once. It hits real APIs and commits the output.

```bash
conda activate auto-job-search
python scripts/generate_fixtures.py
```

`generate_fixtures.py` will:
1. Fetch 3–5 real listings from Adzuna (first query, first location, small page size)
2. Run `extract()` on each — saves `raw_listings.json` + `extracted_listings.json`
3. Run `score()` on each — saves `scored_listings.json`
4. Print which listing to manually clone + edit into `sample_dealbreaker.json`

Regenerate fixtures only when: the Adzuna response schema changes, the extract/score
prompt changes significantly, or you add new extracted fields.

---

## What We Test

### Unit tests (`tests/test_unit.py`)

Pure functions, no I/O, no external calls:

- `make_job_id()` — same input always produces same ID; different inputs differ
- `parse_search_criteria()` — parses the test fixture `.md` correctly
- `_parse_json()` in extract/score — handles: clean JSON, JSON in code fences, bad JSON
- State dedup logic — job IDs already in state are skipped; new ones are not
- Exclude terms filter — titles matching exclude list are dropped

### Integration tests (`tests/test_integration.py`)

Uses fixtures, tests the orchestration layer:

- `run_search.py --dry-run` completes without error against fixture data
- Dealbreaker listings go to `jobs_discarded.json`, not `jobs_scored.json`
- Already-seen job IDs (pre-seeded in a test `state.json`) are skipped
- New listings are written to `listings/{job_id}/listing.json` with correct schema
- `jobs_scored.json` accumulates correctly across two dry-run passes
- State is updated correctly after a run (status transitions)

### Smoke tests (`tests/test_smoke.py`) — manual only

Marked `@pytest.mark.smoke`. These hit real APIs:

- `fetch_all()` returns at least one listing for the primary query
- `extract()` returns valid JSON for a real listing (no parse failure)
- `score()` returns valid scores with both fields in 1–10 range
- Full pipeline run (no `--dry-run`) completes end-to-end for 1 listing

---

## CI Behavior

CI runs `pytest -m "not smoke"` — unit + integration only. No API keys needed.

If integration tests need to write files, they use a `tmp_path` fixture (pytest built-in)
so they never touch the real `data/` directory.

---

## Running Tests Locally

```bash
conda activate auto-job-search
pip install pytest

pytest                        # default: unit + integration
pytest -m smoke               # live run — needs .env with valid keys
pytest -v                     # verbose output
pytest tests/test_unit.py     # one file only
```

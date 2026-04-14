# Auto Job Search — Architecture

## Goal
Two-stage pipeline:
1. **Search & Filter** — fetch listings, score against candidate profile, surface ranked shortlist
2. **Resume Tuning** — tailor base resume per approved listing, one output file per job

## Key Design Decisions
- **Single source**: Adzuna (US coverage, free API 250 req/day, structured JSON, no scraping)
- **Two-score model**: `fit_score` (candidate matches job) + `desirability_score` (job matches candidate) both 1–10
- **Dealbreaker flag**: listings are discarded before scoring; written to `jobs_discarded.json` for audit
- **Two Claude calls per listing**: extract structured fields first, then score — single-purpose calls, reliable JSON
- **`claude --print` via subprocess**: no Anthropic API key needed, uses existing Claude Code session auth
- **File I/O only**: no UI, no notifications. Files are the interface.
- **Idempotent cycles**: `run_search.py` runs identically manual or via cron; state in `data/state.json`
- **Config as markdown**: `search_criteria.md` parsed by Python; `ranking_criteria.md` passed verbatim to Claude

## Directory Structure
```
auto-job-search/
├── config/
│   ├── search_criteria.md       # Adzuna query params (keywords, locations, radius)
│   ├── ranking_criteria.md      # Fit + desirability criteria + candidate profile
│   └── resume_base.md           # Candidate's base resume (plain text, Stage 2 input)
├── data/
│   ├── state.json               # Seen job IDs + lifecycle status (auto-created)
│   ├── jobs_scored.json         # All scored listings from latest cycle (overwritten each run)
│   └── jobs_discarded.json      # Dealbreaker listings (audit trail, appended)
├── listings/
│   └── {job_id}/
│       ├── listing.json         # Raw listing + extracted fields + scores
│       └── resume.md            # Tailored resume output (Stage 2)
├── skills/
│   ├── fetch_listings.py        # Adzuna API wrapper + search_criteria.md parser
│   ├── extract_listing.py       # Claude: extract structured fields from description
│   └── score_listing.py         # Claude: score fit + desirability vs ranking criteria
├── run_search.py                # Orchestrator: fetch → dedupe → extract → score → write
├── review.py                    # CLI: display scored listings, approve/skip, update state
├── tune_resume.py               # Stage 2: generate tailored resume per approved listing
├── setup.py                     # One-time wizard: generates both config files via Claude
├── .env                         # ADZUNA_APP_ID, ADZUNA_API_KEY
├── .env.example
└── requirements.txt
```

## Data Flow — Stage 1

```
search_criteria.md
       │
       ▼
 fetch_listings.py  ──── Adzuna API ────► raw listings (list of dicts)
       │
       ▼
  dedupe against state.json  ──► skip already-seen listings
       │
       ▼ (new listings only)
  extract_listing.py  ──── claude --print ──► extracted fields (license, pay, work type, etc.)
       │
       ▼
  score_listing.py  ──── claude --print ──► {fit_score, desirability_score, dealbreaker, notes}
       │
       ├──► dealbreaker=true  ──► jobs_discarded.json
       │
       └──► dealbreaker=false ──► listings/{job_id}/listing.json
                                  jobs_scored.json
                                  state.json (status: scored)
       │
       ▼
   review.py (manual trigger)
       ├── display listings sorted by fit / desirability
       ├── user: approve / skip each
       └── state.json (status: approved | skipped)
```

## Data Flow — Stage 2

```
state.json (approved listings)
       │
       ▼
  tune_resume.py (manual trigger)
       ├── reads listings/{job_id}/listing.json
       ├── reads config/resume_base.md
       ├── claude --print ──► tailored resume text
       └── writes listings/{job_id}/resume.md
```

## Job Lifecycle
```
new → scored → reviewed → approved | skipped
                                └──► resume_generated  (Stage 2)
```
State tracked in `data/state.json`, keyed by `job_id` = MD5[:12] of `title|company|location`.

## Extracted Fields Schema
```json
{
  "license_required":       "journeyman | master | apprentice | none specified | null",
  "experience_years_min":   2,
  "work_type":              "residential | commercial | industrial | mixed",
  "pay_min":                22.0,
  "pay_max":                30.0,
  "pay_period":             "hourly | annual | null",
  "union":                  true,
  "relocation_assistance":  false,
  "travel_required":        false,
  "apprenticeship_program": false,
  "is_staffing_agency":     false,
  "certifications_required":["OSHA 30"],
  "location":               "Lincoln, NE"
}
```

## Score Schema
```json
{
  "fit_score":          8,
  "desirability_score": 6,
  "dealbreaker":        false,
  "dealbreaker_reason": null,
  "fit_notes":          ["apprentice tier matches", "commercial experience aligns"],
  "desirability_notes": ["pay not listed — uncertainty penalty", "residential only"]
}
```

## listing.json Schema (combined)
```json
{
  "job_id":       "abc123def456",
  "title":        "Apprentice Electrician",
  "company":      "Acme Electric",
  "location":     "Lincoln, NE",
  "url":          "https://...",
  "description":  "...",
  "salary_min":   null,
  "salary_max":   null,
  "posted_date":  "2026-04-13T00:00:00Z",
  "source":       "adzuna",
  "extracted":    { },
  "scores":       { }
}
```

## Config Doc Structure

### search_criteria.md (parsed by Python)
- Queries: keyword list, each runs as a separate Adzuna search
- Exclude terms: filtered by title match before any Claude calls
- Locations: city/state + radius, one or more
- API parameters: results per query, sort order, optional salary floor

### ranking_criteria.md (passed verbatim to Claude)
- Dealbreakers
- Fit criteria (drives fit_score)
- Desirability criteria + weights (drives desirability_score)
- Current situation (baseline for comparison)
- Notes for Claude (free-form judgment context)

## Future Upgrade Path
- Discord bot: thin wrapper, reactions drive approve/skip in state.json
- Additional job sources: extend fetch_listings.py, same downstream pipeline
- Cron scheduling: run_search.py is already idempotent, just add a cron entry

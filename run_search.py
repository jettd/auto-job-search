"""
Orchestrator: fetch → dedupe → extract → score → write files + update state.

Usage:
    python run_search.py             # full run (hits Adzuna + Claude)
    python run_search.py --dry-run   # uses fixtures, skips all API calls

Fixture format (data/fixtures/):
    raw_listings.json        list of listing dicts (same shape as fetch_all() output)
    extracted_listings.json  {job_id: extracted_dict}
    scored_listings.json     {job_id: scores_dict}
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from skills.fetch_listings import fetch_all, parse_search_criteria
from skills.extract_listing import extract
from skills.score_listing import score

ROOT         = Path(__file__).parent
CONFIG_DIR   = ROOT / "config"
DATA_DIR     = ROOT / "data"
LISTINGS_DIR = ROOT / "listings"
FIXTURES_DIR = DATA_DIR / "fixtures"

STATE_PATH    = DATA_DIR / "state.json"
SCORED_PATH   = DATA_DIR / "jobs_scored.json"
DISCARDED_PATH = DATA_DIR / "jobs_discarded.json"


# ---------------------------------------------------------------------------
# State / file helpers
# ---------------------------------------------------------------------------

def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_listing_file(job_id: str, data: dict):
    listing_dir = LISTINGS_DIR / job_id
    listing_dir.mkdir(parents=True, exist_ok=True)
    (listing_dir / "listing.json").write_text(
        json.dumps(data, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Run the job search pipeline.")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Use fixtures instead of live API/Claude calls (for testing)."
    )
    args = parser.parse_args()

    today = date.today().isoformat()

    # --- Load ranking criteria ---
    ranking_criteria = (CONFIG_DIR / "ranking_criteria.md").read_text(encoding="utf-8")

    # --- Fetch or load raw listings ---
    if args.dry_run:
        print("[dry-run] Loading raw listings from fixtures...")
        raw_listings = load_json(FIXTURES_DIR / "raw_listings.json", [])
        fixture_extracted = load_json(FIXTURES_DIR / "extracted_listings.json", {})
        fixture_scored    = load_json(FIXTURES_DIR / "scored_listings.json", {})
    else:
        config = parse_search_criteria(str(CONFIG_DIR / "search_criteria.md"))
        print(
            f"Fetching listings "
            f"({len(config['queries'])} queries × {len(config['locations'])} locations)..."
        )
        raw_listings = fetch_all(
            queries=config["queries"],
            locations=config["locations"],
            exclude_terms=config["exclude_terms"],
            results_per_page=config["results_per_page"],
            salary_min=config["salary_min"],
        )

    print(f"\n{len(raw_listings)} listings fetched.")

    # --- Dedupe against state ---
    state = load_json(STATE_PATH, {})
    new_listings  = [l for l in raw_listings if l["job_id"] not in state]
    already_seen  = len(raw_listings) - len(new_listings)
    print(f"{len(new_listings)} new  |  {already_seen} already seen\n")

    if not new_listings:
        print("Nothing new to process.")
        return

    # --- Process ---
    scored_all = load_json(SCORED_PATH, [])   # accumulate, don't overwrite
    n_scored = n_discarded = n_failed = 0

    for i, listing in enumerate(new_listings, 1):
        job_id = listing["job_id"]
        print(f"[{i}/{len(new_listings)}] {listing['title']} @ {listing['company']}")

        try:
            if args.dry_run:
                extracted = fixture_extracted.get(job_id, {})
                scores    = fixture_scored.get(job_id, {})
            else:
                print("  extracting...", end=" ", flush=True)
                extracted = extract(listing)
                print("scoring...", end=" ", flush=True)
                scores = score(listing, extracted, ranking_criteria)
                print("done.")

            combined = {**listing, "extracted": extracted, "scores": scores}

            if scores.get("dealbreaker"):
                reason = scores.get("dealbreaker_reason", "")
                print(f"  DISCARDED — {reason}")
                discarded = load_json(DISCARDED_PATH, [])
                discarded.append(combined)
                save_json(DISCARDED_PATH, discarded)
                state[job_id] = {
                    "status":     "discarded",
                    "title":      listing["title"],
                    "company":    listing["company"],
                    "location":   listing["location"],
                    "first_seen": today,
                }
                n_discarded += 1
            else:
                fit = scores.get("fit_score", "?")
                des = scores.get("desirability_score", "?")
                print(f"  fit={fit}  desirability={des}")
                write_listing_file(job_id, combined)
                scored_all.append(combined)
                state[job_id] = {
                    "status":     "scored",
                    "title":      listing["title"],
                    "company":    listing["company"],
                    "location":   listing["location"],
                    "first_seen": today,
                }
                n_scored += 1

        except Exception as e:
            print(f"  ERROR — {e}", file=sys.stderr)
            n_failed += 1

        # Save state after every listing so a crash doesn't lose progress
        save_json(STATE_PATH, state)

    save_json(SCORED_PATH, scored_all)

    # --- Summary ---
    print(f"\n--- Run complete ---")
    print(f"  Scored:         {n_scored}")
    print(f"  Discarded:      {n_discarded}")
    print(f"  Failed:         {n_failed}")
    print(f"  Already seen:   {already_seen}")


if __name__ == "__main__":
    main()

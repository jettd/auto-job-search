"""
Generate real test fixtures by running the pipeline against live Adzuna + Claude.
Saves output to data/fixtures/ — commit those files after reviewing them.

Run once (or when API schemas or prompts change significantly):
    conda activate auto-job-search
    python scripts/generate_fixtures.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.fetch_listings import fetch_all, parse_search_criteria
from skills.extract_listing import extract
from skills.score_listing import score

ROOT         = Path(__file__).parent.parent
CONFIG_DIR   = ROOT / "config"
FIXTURES_DIR = ROOT / "data" / "fixtures"

FIXTURE_COUNT = 4  # small enough to be fast, enough to be useful


def main():
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    ranking_criteria = (CONFIG_DIR / "ranking_criteria.md").read_text(encoding="utf-8")
    config = parse_search_criteria(str(CONFIG_DIR / "search_criteria.md"))

    print(f"Fetching up to {FIXTURE_COUNT} listings (first query, first location)...")
    raw_listings = fetch_all(
        queries=[config["queries"][0]],
        locations=[config["locations"][0]],
        exclude_terms=config["exclude_terms"],
        results_per_page=FIXTURE_COUNT,
        salary_min=None,
    )[:FIXTURE_COUNT]

    if not raw_listings:
        print("No listings returned. Check config and API keys.")
        sys.exit(1)

    print(f"\nGot {len(raw_listings)} listings. Extracting and scoring...\n")

    extracted_by_id = {}
    scored_by_id    = {}

    for i, listing in enumerate(raw_listings, 1):
        job_id = listing["job_id"]
        print(f"[{i}/{len(raw_listings)}] {listing['title']} @ {listing['company']}")
        print("  extracting...", end=" ", flush=True)
        extracted = extract(listing)
        print("scoring...", end=" ", flush=True)
        scores = score(listing, extracted, ranking_criteria)
        print("done.")
        extracted_by_id[job_id] = extracted
        scored_by_id[job_id]    = scores

    # Write fixtures
    (FIXTURES_DIR / "raw_listings.json").write_text(
        json.dumps(raw_listings, indent=2), encoding="utf-8"
    )
    (FIXTURES_DIR / "extracted_listings.json").write_text(
        json.dumps(extracted_by_id, indent=2), encoding="utf-8"
    )
    (FIXTURES_DIR / "scored_listings.json").write_text(
        json.dumps(scored_by_id, indent=2), encoding="utf-8"
    )

    print(f"\nFixtures written to {FIXTURES_DIR}/\n")
    print("Summary:")
    for listing in raw_listings:
        s = scored_by_id[listing["job_id"]]
        flag = " [DEALBREAKER]" if s.get("dealbreaker") else \
               f" fit={s.get('fit_score')} des={s.get('desirability_score')}"
        print(f"  {listing['job_id']}  {listing['title']} @ {listing['company']}{flag}")

    has_dealbreaker = any(s.get("dealbreaker") for s in scored_by_id.values())
    if not has_dealbreaker:
        print(
            "\nNone of the fixtures triggered a dealbreaker. The integration tests will"
            "\ncreate a synthetic dealbreaker inline — no manual step needed."
        )

    print("\nNext: git add data/fixtures/ && git commit -m 'add test fixtures'")


if __name__ == "__main__":
    main()

"""
Score a job listing against the candidate's ranking criteria using Claude.

Input:  extracted dict (from extract_listing.py) + raw listing dict
Output: {fit_score, desirability_score, dealbreaker, dealbreaker_reason, fit_notes, desirability_notes}
"""

import json
import subprocess
import sys
from pathlib import Path


EMPTY_RESULT = {
    "fit_score":          0,
    "desirability_score": 0,
    "dealbreaker":        False,
    "dealbreaker_reason": None,
    "fit_notes":          [],
    "desirability_notes": [],
}


def _call_claude(prompt: str) -> str:
    result = subprocess.run(
        ["claude", "--print"],
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude --print failed:\n{result.stderr}")
    return result.stdout.strip()


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        end   = -1 if lines[-1].strip() == "```" else len(lines)
        text  = "\n".join(lines[1:end])
    return json.loads(text)


def score(listing: dict, extracted: dict, ranking_criteria: str) -> dict:
    """
    Score a listing against ranking criteria.
    Returns scoring dict. Falls back to EMPTY_RESULT on parse failure.
    """
    title   = listing.get("title", "")
    company = listing.get("company", "")

    prompt = f"""You are evaluating a job listing for a specific candidate. Read the candidate's criteria and the listing data, then respond with only a JSON object. Do not use tools. Do not explain. Output only the JSON — no text before or after it.

--- CANDIDATE CRITERIA ---
{ranking_criteria}

--- LISTING ---
Title: {title}
Company: {company}
Extracted fields:
{json.dumps(extracted, indent=2)}

--- TASK ---
Score this listing on two dimensions:

fit_score (1-10): How well does the candidate match what this employer wants?
- 9-10: Near-perfect match, candidate clearly qualified
- 7-8: Good match, minor gaps
- 5-6: Partial match, some mismatch
- 3-4: Poor match, significant gaps
- 1-2: Wrong level or type entirely

desirability_score (1-10): How attractive is this job for the candidate?
- 9-10: Excellent opportunity, meets or exceeds all priorities
- 7-8: Good opportunity, meets most priorities
- 5-6: Mixed, some positives and negatives
- 3-4: Below expectations in important areas
- 1-2: Poor fit for candidate's needs

Also check dealbreakers. If any dealbreaker condition is met, set dealbreaker to true and explain why.

Respond with only this JSON:
{{
  "fit_score": 0,
  "desirability_score": 0,
  "dealbreaker": false,
  "dealbreaker_reason": null,
  "fit_notes": ["note 1", "note 2"],
  "desirability_notes": ["note 1", "note 2"]
}}"""

    raw = _call_claude(prompt)

    try:
        return _parse_json(raw)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  [score] JSON parse failed for '{title}': {e}", file=sys.stderr)
        print(f"  [score] Raw output: {raw[:200]}", file=sys.stderr)
        return EMPTY_RESULT.copy()


# --- CLI test ---
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from skills.fetch_listings   import fetch_all, parse_search_criteria
    from skills.extract_listing  import extract

    config_path   = Path(__file__).parent.parent / "config" / "search_criteria.md"
    ranking_path  = Path(__file__).parent.parent / "config" / "ranking_criteria.md"
    config        = parse_search_criteria(str(config_path))
    ranking_criteria = ranking_path.read_text(encoding="utf-8")

    print("Fetching one listing for scoring test...")
    listings = fetch_all(
        queries=[config["queries"][0]],
        locations=[config["locations"][0]],
        exclude_terms=config["exclude_terms"],
        results_per_page=3,
    )

    if not listings:
        print("No listings returned — check fetch config.")
        sys.exit(1)

    listing = listings[0]
    print(f"\nListing: {listing['title']} @ {listing['company']} | {listing['location']}")

    print("Extracting fields...")
    extracted = extract(listing)
    print(json.dumps(extracted, indent=2))

    print("\nScoring...")
    result = score(listing, extracted, ranking_criteria)
    print("\nScore result:")
    print(json.dumps(result, indent=2))

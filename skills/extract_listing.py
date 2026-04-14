"""
Extract structured fields from a raw job listing using Claude.

Input:  listing dict (from fetch_listings.py)
Output: extracted dict with structured fields
"""

import json
import subprocess
import sys
from pathlib import Path


FIELDS = """
- license_required: string or null — e.g. "journeyman", "master", "apprentice", "none specified"
- experience_years_min: integer or null — minimum years explicitly required
- work_type: string — "residential", "commercial", "industrial", or "mixed"
- pay_min: number or null — minimum pay as a plain number, no symbols
- pay_max: number or null — maximum pay as a plain number, no symbols
- pay_period: string or null — "hourly", "annual", or null if not listed
- union: boolean or null — true if union shop, false if explicitly non-union, null if not mentioned
- relocation_assistance: boolean — true if relocation assistance is mentioned
- travel_required: boolean — true if travel is required or expected
- apprenticeship_program: boolean — true if listing mentions apprenticeship, sponsorship, or path to licensure
- is_staffing_agency: boolean — true if this appears to be a staffing/temp agency, not a direct employer
- certifications_required: array of strings — specific certs mentioned, empty array if none
"""

EMPTY_RESULT = {
    "license_required":      None,
    "experience_years_min":  None,
    "work_type":             "mixed",
    "pay_min":               None,
    "pay_max":               None,
    "pay_period":            None,
    "union":                 None,
    "relocation_assistance": False,
    "travel_required":       False,
    "apprenticeship_program":False,
    "is_staffing_agency":    False,
    "certifications_required": [],
    "location": "",
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
    """Parse JSON from Claude output, stripping code fences if present."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        end   = -1 if lines[-1].strip() == "```" else len(lines)
        text  = "\n".join(lines[1:end])
    return json.loads(text)


def extract(listing: dict) -> dict:
    """
    Extract structured fields from a listing's title + description.
    Returns extracted dict. Falls back to EMPTY_RESULT on parse failure.
    """
    title       = listing.get("title", "")
    company     = listing.get("company", "")
    description = listing.get("description", "")

    # Include any salary data Adzuna already provided as a hint
    salary_hint = ""
    if listing.get("salary_min") or listing.get("salary_max"):
        salary_hint = (
            f"\nAdzuna salary data (annual): "
            f"min={listing.get('salary_min')}, max={listing.get('salary_max')}"
        )

    prompt = f"""Read this job listing and respond with only a JSON object. Do not use tools. Do not explain. Output only the JSON — no text before or after it.

Job Title: {title}
Company: {company}
Description:
{description}{salary_hint}

Extract the following fields:
{FIELDS}
Respond with only this JSON structure (use null or false for unknown fields):
{{
  "license_required": null,
  "experience_years_min": null,
  "work_type": "mixed",
  "pay_min": null,
  "pay_max": null,
  "pay_period": null,
  "union": null,
  "relocation_assistance": false,
  "travel_required": false,
  "apprenticeship_program": false,
  "is_staffing_agency": false,
  "certifications_required": []
}}"""

    raw = _call_claude(prompt)

    try:
        result = _parse_json(raw)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  [extract] JSON parse failed for '{title}': {e}", file=sys.stderr)
        print(f"  [extract] Raw output: {raw[:200]}", file=sys.stderr)
        result = EMPTY_RESULT.copy()

    result["location"] = listing.get("location", "")
    return result


# --- CLI test ---
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from skills.fetch_listings import fetch_all, parse_search_criteria

    config_path = Path(__file__).parent.parent / "config" / "search_criteria.md"
    config      = parse_search_criteria(str(config_path))

    print("Fetching one listing for extraction test...")
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
    print(f"\nListing: {listing['title']} @ {listing['company']}")
    print(f"Description snippet: {listing['description'][:200]}...")
    print("\nExtracting fields...")

    extracted = extract(listing)
    print("\nExtracted:")
    print(json.dumps(extracted, indent=2))

"""
Fetch job listings from Adzuna API.

Input:  query (str), location (str), radius_miles (int), results_per_page (int)
Output: list of normalized listing dicts
"""

import os
import hashlib
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()

ADZUNA_APP_ID  = os.getenv("ADZUNA_APP_ID")
ADZUNA_API_KEY = os.getenv("ADZUNA_API_KEY")
BASE_URL       = "https://api.adzuna.com/v1/api/jobs/us/search/1"


def make_job_id(title: str, company: str, location: str) -> str:
    """Stable ID from normalized title+company+location."""
    raw = f"{title.lower().strip()}|{company.lower().strip()}|{location.lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def fetch(query: str, location: str, radius_miles: int = 50,
          results_per_page: int = 25, salary_min: int = None) -> list[dict]:
    """
    Fetch listings from Adzuna for a single query+location.
    Returns a list of normalized listing dicts.
    """
    params = {
        "app_id":           ADZUNA_APP_ID,
        "app_key":          ADZUNA_API_KEY,
        "results_per_page": results_per_page,
        "what":             query,
        "where":            location,
        "distance":         radius_miles,
        "sort_by":          "date",
        "content-type":     "application/json",
    }
    if salary_min:
        params["salary_min"] = salary_min

    resp = requests.get(BASE_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    listings = []
    for job in data.get("results", []):
        company  = job.get("company", {}).get("display_name", "") or ""
        title    = job.get("title", "") or ""
        location_str = job.get("location", {}).get("display_name", "") or ""

        listing = {
            "job_id":       make_job_id(title, company, location_str),
            "title":        title,
            "company":      company,
            "location":     location_str,
            "url":          job.get("redirect_url", ""),
            "description":  job.get("description", ""),
            "salary_min":   job.get("salary_min"),
            "salary_max":   job.get("salary_max"),
            "posted_date":  job.get("created", ""),
            "category":     job.get("category", {}).get("label", ""),
            "source":       "adzuna",
            "query_used":   query,
        }
        listings.append(listing)

    return listings


def parse_search_criteria(path: str) -> dict:
    """
    Parse search_criteria.md into a structured dict.
    Returns: {queries, exclude_terms, locations, results_per_page, salary_min}
    """
    text = Path(path).read_text(encoding="utf-8")

    queries        = []
    exclude_terms  = []
    locations      = []
    results_per_page = 25
    salary_min     = None

    section      = None
    subsection   = None
    pending_city = None

    for raw_line in text.split("\n"):
        line = raw_line.strip()

        # Skip comments (# but not ## section headers)
        if line.startswith("#") and not line.startswith("##"):
            continue

        if line.startswith("## "):
            section      = line[3:].lower().split("(")[0].strip()
            subsection   = None
            pending_city = None
            continue

        if section == "queries":
            low = line.lower()
            if "primary keywords" in low:
                subsection = "primary"
            elif "exclude terms" in low:
                subsection = "exclude"
            elif line.startswith("- "):
                term = line[2:].strip().strip('"')
                if subsection == "primary":
                    queries.append(term)
                elif subsection == "exclude":
                    exclude_terms.append(term)

        elif section in ("locations", "additional locations"):
            low = line.lower()
            if low.startswith("- city:"):
                pending_city = line.split(":", 1)[1].strip()
            elif low.startswith("- radius:") and pending_city:
                radius_str = line.split(":", 1)[1].strip().split()[0]
                try:
                    radius = int(radius_str)
                except ValueError:
                    radius = 50
                locations.append({"city": pending_city, "radius": radius})
                pending_city = None

        elif section == "api parameters":
            low = line.lower()
            if low.startswith("- results per query"):
                val = line.split(":", 1)[1].strip()
                try:
                    results_per_page = int(val)
                except ValueError:
                    pass
            elif low.startswith("- salary floor"):
                val = line.split(":", 1)[1].strip()
                if val:
                    cleaned = val.replace(",", "").replace("$", "").split()[0]
                    try:
                        salary_min = int(cleaned)
                    except ValueError:
                        pass

    return {
        "queries":          queries,
        "exclude_terms":    exclude_terms,
        "locations":        locations,
        "results_per_page": results_per_page,
        "salary_min":       salary_min,
    }


def fetch_all(queries: list[str], locations: list[dict],
              exclude_terms: list[str] = None,
              results_per_page: int = 25, salary_min: int = None) -> list[dict]:
    """
    Run all query × location combinations, merge results, dedup by job_id.
    locations:     list of {"city": str, "radius": int}
    exclude_terms: titles containing any of these (case-insensitive) are dropped
    """
    exclude_lower = [t.lower() for t in (exclude_terms or [])]
    seen_ids      = set()
    all_listings  = []

    for query in queries:
        for loc in locations:
            city   = loc["city"]
            radius = loc.get("radius", 50)
            print(f"  Fetching: '{query}' near '{city}' ({radius}mi)...")
            try:
                results  = fetch(query, city, radius, results_per_page, salary_min)
                new = excluded = dupes = 0
                for listing in results:
                    title_low = listing["title"].lower()
                    if any(ex in title_low for ex in exclude_lower):
                        excluded += 1
                        continue
                    if listing["job_id"] in seen_ids:
                        dupes += 1
                        continue
                    seen_ids.add(listing["job_id"])
                    all_listings.append(listing)
                    new += 1
                print(f"    {new} new  |  {excluded} excluded by title  |  {dupes} dupes dropped")
            except requests.HTTPError as e:
                print(f"    ERROR: {e}")

    return all_listings


# --- CLI test ---
if __name__ == "__main__":
    config_path = Path(__file__).parent.parent / "config" / "search_criteria.md"
    config      = parse_search_criteria(str(config_path))

    print(f"Queries:       {config['queries']}")
    print(f"Exclude terms: {config['exclude_terms']}")
    print(f"Locations:     {config['locations']}")
    print(f"Results/query: {config['results_per_page']}")
    print()

    results = fetch_all(
        queries=config["queries"],
        locations=config["locations"],
        exclude_terms=config["exclude_terms"],
        results_per_page=config["results_per_page"],
        salary_min=config["salary_min"],
    )

    print(f"\nTotal: {len(results)} listings")
    for r in results:
        pay = f"${r['salary_min']:.0f}-${r['salary_max']:.0f}" if r["salary_min"] else "no pay listed"
        print(f"  [{r['job_id']}] {r['title']} @ {r['company']} | {r['location']} | {pay}")

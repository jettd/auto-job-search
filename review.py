"""
Terminal review CLI for scored job listings.

Usage:
    python review.py              # sort by fit score (default)
    python review.py --sort des   # sort by desirability score

Controls during review:
    y  — approve listing
    s  — skip listing
    f  — re-sort by fit score (resets to top of remaining)
    d  — re-sort by desirability score (resets to top of remaining)
    q  — quit (progress is saved)
"""

import argparse
import json
import sys
from pathlib import Path

ROOT        = Path(__file__).parent
DATA_DIR    = ROOT / "data"
STATE_PATH  = DATA_DIR / "state.json"
SCORED_PATH = DATA_DIR / "jobs_scored.json"

WIDTH = 62


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def fmt_pay(ex: dict) -> str:
    lo     = ex.get("pay_min")
    hi     = ex.get("pay_max")
    period = ex.get("pay_period") or ""
    suffix = f"/{period}" if period else ""
    if lo and hi:
        return f"${lo:.0f}–${hi:.0f}{suffix}"
    if lo:
        return f"${lo:.0f}+{suffix}"
    return "not listed"


def fmt_bool(val, yes="yes", no="no", unknown="—") -> str:
    if val is True:  return yes
    if val is False: return no
    return unknown


def pending_listings(scored: list, state: dict, sort_key: str) -> list:
    """Return unreviewed listings sorted by score."""
    score_field = "fit_score" if sort_key == "fit" else "desirability_score"
    unreviewed = [
        l for l in scored
        if state.get(l["job_id"], {}).get("status") == "scored"
    ]
    return sorted(
        unreviewed,
        key=lambda l: l.get("scores", {}).get(score_field, 0),
        reverse=True,
    )


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def display_listing(listing: dict, index: int, total: int, sort_key: str):
    ex = listing.get("extracted", {})
    sc = listing.get("scores", {})

    sep = "─" * WIDTH
    print(f"\n{sep}")
    print(f"[{index}/{total}]  {listing['title']} @ {listing['company']}")
    print(f"         {listing['location']}  |  {str(listing.get('posted_date', ''))[:10]}")
    print(f"         fit={sc.get('fit_score', '?')}  "
          f"desirability={sc.get('desirability_score', '?')}")

    print()
    print(f"  Pay       {fmt_pay(ex)}")
    print(f"  Work      {ex.get('work_type') or '—'}")
    print(f"  License   {ex.get('license_required') or '—'}")
    print(f"  Union     {fmt_bool(ex.get('union'))}")
    print(f"  Travel    {fmt_bool(ex.get('travel_required'))}")
    print(f"  Agency    {fmt_bool(ex.get('is_staffing_agency'))}")

    certs = ex.get("certifications_required") or []
    if certs:
        print(f"  Certs     {', '.join(certs)}")

    summary = ex.get("summary", "").strip()
    if summary:
        print(f"\n  {summary}")

    fit_notes = sc.get("fit_notes") or []
    des_notes = sc.get("desirability_notes") or []
    if fit_notes:
        print("\n  Fit:")
        for note in fit_notes:
            print(f"    • {note}")
    if des_notes:
        print("\n  Desirability:")
        for note in des_notes:
            print(f"    • {note}")

    url = listing.get("url", "")
    if url:
        print(f"\n  {url}")

    print(sep)
    print(f"  sorting by {sort_key}  |  "
          "(y) approve  (s) skip  (f) sort:fit  (d) sort:des  (q) quit")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Review scored job listings.")
    parser.add_argument(
        "--sort", choices=["fit", "des"], default="fit",
        help="Initial sort order (default: fit score)"
    )
    args = parser.parse_args()
    sort_key = args.sort

    state  = load_json(STATE_PATH, {})
    scored = load_json(SCORED_PATH, [])

    queue = pending_listings(scored, state, sort_key)

    if not queue:
        print("No listings pending review. Run run_search.py to fetch new listings.")
        return

    print(f"{len(queue)} listings pending review.")

    approved = skipped = 0
    i = 0

    while i < len(queue):
        listing = queue[i]
        display_listing(listing, i + 1, len(queue), sort_key)

        try:
            cmd = input("\n> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nInterrupted — progress saved.")
            break

        if cmd == "q":
            print("Quit — progress saved.")
            break

        elif cmd == "y":
            state[listing["job_id"]]["status"] = "approved"
            save_json(STATE_PATH, state)
            approved += 1
            i += 1

        elif cmd in ("s", "n"):
            state[listing["job_id"]]["status"] = "skipped"
            save_json(STATE_PATH, state)
            skipped += 1
            i += 1

        elif cmd in ("f", "d"):
            sort_key = "fit" if cmd == "f" else "des"
            # Reload remaining unreviewed and re-sort from top
            queue = pending_listings(scored, state, sort_key)
            i = 0
            print(f"  Re-sorted by {sort_key}. {len(queue)} remaining.")

        else:
            print("  ? y=approve  s=skip  f=sort:fit  d=sort:des  q=quit")

    remaining = len(queue) - i
    print(f"\nSession: {approved} approved, {skipped} skipped, {remaining} remaining.")


if __name__ == "__main__":
    main()

"""
Archive jobs_scored.json and clear it for the next review cycle.

Copies jobs_scored.json → data/archive/jobs_scored_{date}.json
Appends all entries to data/jobs_master.json (cumulative history)
Then clears jobs_scored.json to give review.py a clean slate.

Usage:
    python rotate.py
    python rotate.py --dry-run   # show what would happen, write nothing
"""

import argparse
import json
from datetime import date
from pathlib import Path

ROOT           = Path(__file__).parent
DATA_DIR       = ROOT / "data"
ARCHIVE_DIR    = DATA_DIR / "archive"
SCORED_PATH    = DATA_DIR / "jobs_scored.json"
MASTER_PATH    = DATA_DIR / "jobs_master.json"


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Rotate jobs_scored.json for next review cycle.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without writing anything.")
    args = parser.parse_args()

    scored = load_json(SCORED_PATH, [])

    if not scored:
        print("jobs_scored.json is empty or missing — nothing to rotate.")
        return

    archive_name = f"jobs_scored_{date.today().isoformat()}.json"
    archive_path = ARCHIVE_DIR / archive_name

    # Warn if archive file already exists (two rotations on same day)
    if archive_path.exists() and not args.dry_run:
        existing = load_json(archive_path, [])
        archive_name = f"jobs_scored_{date.today().isoformat()}_{len(existing)}+{len(scored)}.json"
        archive_path = ARCHIVE_DIR / archive_name

    master = load_json(MASTER_PATH, [])
    master_ids = {l["job_id"] for l in master}
    new_to_master = [l for l in scored if l["job_id"] not in master_ids]

    print(f"Scored listings:     {len(scored)}")
    print(f"Archive destination: data/archive/{archive_name}")
    print(f"New to master log:   {len(new_to_master)}")
    print(f"Already in master:   {len(scored) - len(new_to_master)}")

    if args.dry_run:
        print("\n[dry-run] No files written.")
        return

    save_json(archive_path, scored)
    save_json(MASTER_PATH, master + new_to_master)
    save_json(SCORED_PATH, [])

    print(f"\nArchived  → data/archive/{archive_name}")
    print(f"Appended  → data/jobs_master.json ({len(master) + len(new_to_master)} total)")
    print(f"Cleared   → data/jobs_scored.json")


if __name__ == "__main__":
    main()

"""
Shared fixtures for the test suite.
"""
import json
import shutil
from pathlib import Path

import pytest

ROOT         = Path(__file__).parent.parent
DATA_DIR     = ROOT / "data"
LISTINGS_DIR = ROOT / "listings"
FIXTURES_DIR = DATA_DIR / "fixtures"

STATE_PATH     = DATA_DIR / "state.json"
SCORED_PATH    = DATA_DIR / "jobs_scored.json"
DISCARDED_PATH = DATA_DIR / "jobs_discarded.json"


def _fixture_job_ids() -> set:
    raw = FIXTURES_DIR / "raw_listings.json"
    if not raw.exists():
        return set()
    return {l["job_id"] for l in json.loads(raw.read_text())}


@pytest.fixture
def clean_run_env():
    """
    Before each integration test: back up runtime files and ensure a clean slate.
    After: remove files written during the test, restore backups.
    Only touches files related to fixture job IDs — leaves any real user data alone.
    """
    job_ids = _fixture_job_ids()

    # --- Back up state entries for fixture job IDs ---
    state = {}
    state_backup = {}
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text())
        state_backup = {k: v for k, v in state.items() if k in job_ids}
        for jid in job_ids:
            state.pop(jid, None)
        STATE_PATH.write_text(json.dumps(state, indent=2))

    # --- Back up and clear jobs_scored entries for fixture IDs ---
    scored_backup = []
    if SCORED_PATH.exists():
        all_scored = json.loads(SCORED_PATH.read_text())
        scored_backup = [l for l in all_scored if l["job_id"] in job_ids]
        remainder = [l for l in all_scored if l["job_id"] not in job_ids]
        SCORED_PATH.write_text(json.dumps(remainder, indent=2))

    # --- Back up and clear jobs_discarded entries for fixture IDs ---
    discarded_backup = []
    if DISCARDED_PATH.exists():
        all_disc = json.loads(DISCARDED_PATH.read_text())
        discarded_backup = [l for l in all_disc if l["job_id"] in job_ids]
        remainder = [l for l in all_disc if l["job_id"] not in job_ids]
        DISCARDED_PATH.write_text(json.dumps(remainder, indent=2))

    yield

    # --- Clean up listing dirs created during test ---
    for jid in job_ids:
        listing_dir = LISTINGS_DIR / jid
        if listing_dir.exists():
            shutil.rmtree(listing_dir)

    # --- Remove fixture entries from output files ---
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text())
        for jid in job_ids:
            state.pop(jid, None)
        state.update(state_backup)
        STATE_PATH.write_text(json.dumps(state, indent=2))

    if SCORED_PATH.exists():
        all_scored = json.loads(SCORED_PATH.read_text())
        cleaned = [l for l in all_scored if l["job_id"] not in job_ids]
        cleaned.extend(scored_backup)
        SCORED_PATH.write_text(json.dumps(cleaned, indent=2))

    if DISCARDED_PATH.exists():
        all_disc = json.loads(DISCARDED_PATH.read_text())
        cleaned = [l for l in all_disc if l["job_id"] not in job_ids]
        cleaned.extend(discarded_backup)
        DISCARDED_PATH.write_text(json.dumps(cleaned, indent=2))

"""
Integration tests — uses real fixtures, no external API calls.
All file I/O goes to the real data/ and listings/ directories;
conftest.clean_run_env handles backup and cleanup.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT         = Path(__file__).parent.parent
DATA_DIR     = ROOT / "data"
LISTINGS_DIR = ROOT / "listings"
FIXTURES_DIR = DATA_DIR / "fixtures"

STATE_PATH     = DATA_DIR / "state.json"
SCORED_PATH    = DATA_DIR / "jobs_scored.json"
DISCARDED_PATH = DATA_DIR / "jobs_discarded.json"


def run_dry():
    """Run run_search.py --dry-run and return the CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(ROOT / "run_search.py"), "--dry-run"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )


def load_fixture_job_ids() -> dict:
    """Return {job_id: scores} for all fixture listings."""
    raw      = json.loads((FIXTURES_DIR / "raw_listings.json").read_text())
    scored   = json.loads((FIXTURES_DIR / "scored_listings.json").read_text())
    return {l["job_id"]: scored.get(l["job_id"], {}) for l in raw}


# ---------------------------------------------------------------------------
# Basic run
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_dry_run_exits_cleanly(clean_run_env):
    result = run_dry()
    assert result.returncode == 0, f"run_search.py exited non-zero:\n{result.stderr}"


@pytest.mark.integration
def test_dry_run_state_updated(clean_run_env):
    run_dry()
    assert STATE_PATH.exists(), "state.json was not created"
    state = json.loads(STATE_PATH.read_text())
    fixture_ids = load_fixture_job_ids()
    for jid in fixture_ids:
        assert jid in state, f"job_id {jid} missing from state"


# ---------------------------------------------------------------------------
# Routing: scored vs discarded
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_scored_listings_written_to_file(clean_run_env):
    run_dry()
    fixture_ids = load_fixture_job_ids()
    scored_ids = {jid for jid, s in fixture_ids.items() if not s.get("dealbreaker")}

    assert SCORED_PATH.exists(), "jobs_scored.json was not created"
    scored = json.loads(SCORED_PATH.read_text())
    written_ids = {l["job_id"] for l in scored}

    for jid in scored_ids:
        assert jid in written_ids, f"scored job {jid} missing from jobs_scored.json"


@pytest.mark.integration
def test_scored_listings_have_listing_files(clean_run_env):
    run_dry()
    fixture_ids = load_fixture_job_ids()
    scored_ids = {jid for jid, s in fixture_ids.items() if not s.get("dealbreaker")}

    for jid in scored_ids:
        listing_file = LISTINGS_DIR / jid / "listing.json"
        assert listing_file.exists(), f"listings/{jid}/listing.json not written"
        data = json.loads(listing_file.read_text())
        assert "extracted" in data
        assert "scores" in data


@pytest.mark.integration
def test_dealbreakers_go_to_discarded(clean_run_env):
    run_dry()
    fixture_ids = load_fixture_job_ids()
    dealbreaker_ids = {jid for jid, s in fixture_ids.items() if s.get("dealbreaker")}

    if not dealbreaker_ids:
        pytest.skip("No dealbreakers in current fixtures")

    assert DISCARDED_PATH.exists(), "jobs_discarded.json was not created"
    discarded = json.loads(DISCARDED_PATH.read_text())
    written_ids = {l["job_id"] for l in discarded}

    for jid in dealbreaker_ids:
        assert jid in written_ids, f"dealbreaker {jid} missing from jobs_discarded.json"


@pytest.mark.integration
def test_dealbreakers_not_in_scored(clean_run_env):
    run_dry()
    fixture_ids = load_fixture_job_ids()
    dealbreaker_ids = {jid for jid, s in fixture_ids.items() if s.get("dealbreaker")}

    if not dealbreaker_ids or not SCORED_PATH.exists():
        pytest.skip("No dealbreakers or no scored file")

    scored = json.loads(SCORED_PATH.read_text())
    scored_ids = {l["job_id"] for l in scored}

    for jid in dealbreaker_ids:
        assert jid not in scored_ids, f"dealbreaker {jid} leaked into jobs_scored.json"


@pytest.mark.integration
def test_state_statuses_correct(clean_run_env):
    run_dry()
    state = json.loads(STATE_PATH.read_text())
    fixture_ids = load_fixture_job_ids()

    for jid, scores in fixture_ids.items():
        entry = state[jid]
        if scores.get("dealbreaker"):
            assert entry["status"] == "discarded", f"{jid} should be discarded in state"
        else:
            assert entry["status"] == "scored", f"{jid} should be scored in state"


# ---------------------------------------------------------------------------
# Dedup: second run skips already-seen listings
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_second_run_skips_seen_listings(clean_run_env):
    run_dry()

    # Capture scored count after first run
    scored_after_first = []
    if SCORED_PATH.exists():
        scored_after_first = json.loads(SCORED_PATH.read_text())

    # Second run
    result = run_dry()
    assert result.returncode == 0

    # Output should say "Nothing new to process"
    assert "Nothing new" in result.stdout, \
        f"Expected second run to skip all listings, got:\n{result.stdout}"

    # Scored file should be unchanged
    if SCORED_PATH.exists():
        scored_after_second = json.loads(SCORED_PATH.read_text())
        assert len(scored_after_second) == len(scored_after_first)


# ---------------------------------------------------------------------------
# Accumulation: scored file grows across runs
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_scored_file_accumulates(clean_run_env):
    """Seeding state with half the fixtures then running should only add the other half."""
    fixture_ids = load_fixture_job_ids()
    all_ids = list(fixture_ids.keys())
    if len(all_ids) < 2:
        pytest.skip("Need at least 2 fixture listings")

    # Pre-seed state with the first listing as already seen
    pre_seen_id = all_ids[0]
    state = {pre_seen_id: {"status": "scored", "title": "x", "company": "x",
                            "location": "x", "first_seen": "2000-01-01"}}
    STATE_PATH.write_text(json.dumps(state, indent=2))

    run_dry()

    scored = json.loads(SCORED_PATH.read_text()) if SCORED_PATH.exists() else []
    scored_ids = {l["job_id"] for l in scored}

    # pre-seen listing should not be in scored output (it was skipped)
    if not fixture_ids[pre_seen_id].get("dealbreaker"):
        assert pre_seen_id not in scored_ids, \
            "Pre-seeded listing should have been skipped, not re-scored"

"""
Unit tests — pure functions, no external calls.
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys_path_insert = __import__("sys").path.insert(0, str(ROOT))

from skills.fetch_listings import make_job_id, parse_search_criteria
from skills.extract_listing import _parse_json, EMPTY_RESULT

FIXTURES_DIR = ROOT / "data" / "fixtures"
TEST_CRITERIA = FIXTURES_DIR / "search_criteria_test.md"


# ---------------------------------------------------------------------------
# make_job_id
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_make_job_id_deterministic():
    a = make_job_id("Apprentice Electrician", "Acme Electric", "Lincoln, NE")
    b = make_job_id("Apprentice Electrician", "Acme Electric", "Lincoln, NE")
    assert a == b


@pytest.mark.unit
def test_make_job_id_unique_on_different_inputs():
    a = make_job_id("Apprentice Electrician", "Acme Electric", "Lincoln, NE")
    b = make_job_id("Journeyman Electrician", "Acme Electric", "Lincoln, NE")
    assert a != b


@pytest.mark.unit
def test_make_job_id_normalizes_case_and_whitespace():
    a = make_job_id("  Apprentice Electrician  ", "Acme Electric", "Lincoln, NE")
    b = make_job_id("apprentice electrician", "acme electric", "lincoln, ne")
    assert a == b


@pytest.mark.unit
def test_make_job_id_length():
    jid = make_job_id("Apprentice Electrician", "Acme Electric", "Lincoln, NE")
    assert len(jid) == 12


# ---------------------------------------------------------------------------
# parse_search_criteria
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_parse_search_criteria_queries():
    config = parse_search_criteria(str(TEST_CRITERIA))
    assert "electrician apprentice" in config["queries"]
    assert "journeyman electrician" in config["queries"]


@pytest.mark.unit
def test_parse_search_criteria_exclude_terms():
    config = parse_search_criteria(str(TEST_CRITERIA))
    assert "master electrician" in config["exclude_terms"]
    assert "superintendent" in config["exclude_terms"]


@pytest.mark.unit
def test_parse_search_criteria_locations():
    config = parse_search_criteria(str(TEST_CRITERIA))
    assert len(config["locations"]) == 1
    assert config["locations"][0]["city"] == "Lincoln, NE"
    assert config["locations"][0]["radius"] == 50


@pytest.mark.unit
def test_parse_search_criteria_api_params():
    config = parse_search_criteria(str(TEST_CRITERIA))
    assert config["results_per_page"] == 10
    assert config["salary_min"] == 18


# ---------------------------------------------------------------------------
# _parse_json
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_parse_json_clean():
    raw = '{"fit_score": 8, "dealbreaker": false}'
    result = _parse_json(raw)
    assert result["fit_score"] == 8
    assert result["dealbreaker"] is False


@pytest.mark.unit
def test_parse_json_strips_code_fence():
    raw = '```json\n{"fit_score": 7}\n```'
    result = _parse_json(raw)
    assert result["fit_score"] == 7


@pytest.mark.unit
def test_parse_json_strips_unlabeled_fence():
    raw = '```\n{"fit_score": 5}\n```'
    result = _parse_json(raw)
    assert result["fit_score"] == 5


@pytest.mark.unit
def test_parse_json_bad_input_raises():
    with pytest.raises((json.JSONDecodeError, ValueError)):
        _parse_json("this is not json at all")


# ---------------------------------------------------------------------------
# EMPTY_RESULT schema
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_empty_result_has_required_keys():
    required = {
        "license_required", "experience_years_min", "work_type",
        "pay_min", "pay_max", "pay_period", "union",
        "relocation_assistance", "travel_required",
        "apprenticeship_program", "is_staffing_agency",
        "certifications_required", "summary", "location",
    }
    assert required.issubset(EMPTY_RESULT.keys())

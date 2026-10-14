"""Tests for parse_study. Run them with: pytest"""

from app.ingest.ctgov import parse_study

# A small fake trial shaped like a real API response, so we can test
# without using the internet.
SAMPLE = {
    "protocolSection": {
        "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Sample T2D trial"},
        "statusModule": {"overallStatus": "RECRUITING"},
        "designModule": {"studyType": "INTERVENTIONAL"},
        "conditionsModule": {"conditions": ["Type 2 Diabetes"]},
        "eligibilityModule": {
            "eligibilityCriteria": "Inclusion:\n- HbA1c 7-10%\nExclusion:\n- eGFR < 30",
            "sex": "ALL",
            "minimumAge": "18 Years",
            "maximumAge": "75 Years",
            "healthyVolunteers": False,
        },
    }
}


def test_parse_study_extracts_fields() -> None:
    # A normal trial: the fields we care about should be copied correctly.
    rec = parse_study(SAMPLE)
    assert rec is not None
    assert rec.nct_id == "NCT00000001"
    assert rec.min_age == "18 Years"
    assert "HbA1c" in rec.eligibility_text


def test_parse_study_skips_missing_eligibility() -> None:
    # A trial with no eligibility text is useless to us, so it should be skipped.
    no_text = {"protocolSection": {"identificationModule": {"nctId": "NCT2"}}}
    assert parse_study(no_text) is None
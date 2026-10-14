"""Tests for fetch_trials, using a fake API so no internet is needed."""

from typing import Any

import pytest

from app.ingest import ctgov


# Builds a tiny fake trial. study_type lets us make non-treatment ones too.
def make_study(nct_id: str, study_type: str = "INTERVENTIONAL") -> dict[str, Any]:
    return {
        "protocolSection": {
            "identificationModule": {"nctId": nct_id, "briefTitle": "t"},
            "designModule": {"studyType": study_type},
            "eligibilityModule": {"eligibilityCriteria": "some criteria"},
        }
    }


# Pretends to be the web reply that requests.get() would normally return.
class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


def test_fetch_trials_paginates_and_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    # Two fake pages: page 1 has a treatment trial, an observational trial (should
    # be skipped) and a token for the next page; page 2 has one more trial.
    pages: list[dict[str, Any]] = [
        {
            "studies": [make_study("NCT1"), make_study("NCT2", "OBSERVATIONAL")],
            "nextPageToken": "abc",
        },
        {"studies": [make_study("NCT3")]},
    ]
    calls: list[dict[str, Any]] = []  # remembers the options of each request

    def fake_get(url: str, params: dict[str, Any], timeout: int) -> FakeResponse:
        calls.append(dict(params))
        return FakeResponse(pages[len(calls) - 1])

    # monkeypatch swaps the real internet call for our fake, just for this test.
    monkeypatch.setattr("app.ingest.ctgov.requests.get", fake_get)
    monkeypatch.setattr("app.ingest.ctgov.time.sleep", lambda _: None)

    records = ctgov.fetch_trials("type 2 diabetes", limit=10)

    # We should get NCT1 and NCT3; the observational NCT2 is filtered out.
    assert [r.nct_id for r in records] == ["NCT1", "NCT3"]
    # The first request has no page token; the second uses the one from page 1.
    assert "pageToken" not in calls[0]
    assert calls[1]["pageToken"] == "abc"
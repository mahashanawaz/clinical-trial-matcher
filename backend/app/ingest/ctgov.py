"""
ctgov.py - Download clinical trials from ClinicalTrials.gov.

What this file does, in 3 steps:
1. Ask the free ClinicalTrials.gov API for trials that are recruiting patients.
2. Pick out only the fields we need (title, age limits, eligibility text...).
3. Save the cleaned trials to a JSON file for the next stage of the project.

Run it from the backend folder:
    python -m app.ingest.ctgov --condition "type 2 diabetes" --limit 40
"""

from __future__ import annotations

import argparse  # reads options typed in the terminal (like --limit 40)
import json  # saves our data as a .json file
import time  # lets us pause between requests
from pathlib import Path  # a clean way to work with file paths
from typing import Any  # "Any" means "could be any type" (used for raw API data)

import requests  # sends web requests to the API
from pydantic import BaseModel  # checks that our data has the right shape/types

# The web address of the ClinicalTrials.gov API (free, no key needed).
BASE_URL = "https://clinicaltrials.gov/api/v2/studies"


class TrialRecord(BaseModel):
    """One clean clinical trial.

    The API gives us a huge, messy record. This class describes the small,
    tidy version we keep. Pydantic raises an error if a value has the wrong
    type, so bad data can't sneak into the rest of the project.
    """

    nct_id: str  # the trial's unique ID, like "NCT01234567"
    title: str
    status: str  # e.g. "RECRUITING"
    study_type: str | None = None  # "str | None" means text OR empty
    conditions: list[str] = []  # diseases the trial studies
    sex: str | None = None  # "ALL", "MALE" or "FEMALE"
    min_age: str | None = None  # kept as text, e.g. "18 Years"
    max_age: str | None = None
    healthy_volunteers: bool | None = None  # True/False if healthy people can join
    eligibility_text: str  # the long inclusion/exclusion rules (our key data)


def parse_study(study: dict[str, Any]) -> TrialRecord | None:
    """Turn one raw API result into a clean TrialRecord.

    Returns None if the trial has no eligibility text, since our whole
    project depends on that text.
    """
    # The API nests data in layers, like folders inside folders.
    # .get("name", {}) opens a layer, and gives an empty one if it's missing
    # (instead of crashing).
    proto = study.get("protocolSection", {})
    ident = proto.get("identificationModule", {})
    elig = proto.get("eligibilityModule", {})

    text = elig.get("eligibilityCriteria")
    nct_id = ident.get("nctId")

    # No eligibility text or no ID? Skip this trial.
    if not text or not nct_id:
        return None

    # Build the clean record, copying each field from the right layer.
    return TrialRecord(
        nct_id=nct_id,
        title=ident.get("briefTitle", ""),
        status=proto.get("statusModule", {}).get("overallStatus", "UNKNOWN"),
        study_type=proto.get("designModule", {}).get("studyType"),
        conditions=proto.get("conditionsModule", {}).get("conditions", []),
        sex=elig.get("sex"),
        min_age=elig.get("minimumAge"),
        max_age=elig.get("maximumAge"),
        healthy_volunteers=elig.get("healthyVolunteers"),
        eligibility_text=text,
    )


def fetch_trials(condition: str, limit: int, page_size: int = 50) -> list[TrialRecord]:
    """Download up to `limit` recruiting treatment trials for a condition.

    The API sends results in "pages" (like search result pages), so we loop:
    read a page, keep the good trials, then ask for the next page.
    """
    records: list[TrialRecord] = []  # our growing list of clean trials

    # The options we send to the API (these become the ?key=value part of the URL).
    params: dict[str, str | int] = {
        "query.cond": condition,  # which disease to search for
        "filter.overallStatus": "RECRUITING",  # only trials still accepting patients
        "pageSize": page_size,  # how many trials per page
    }

    while len(records) < limit:  # keep going until we have enough trials
        resp = requests.get(BASE_URL, params=params, timeout=30)  # ask the API
        resp.raise_for_status()  # stop with an error if the request failed
        data = resp.json()  # convert the reply into a Python dictionary

        for study in data.get("studies", []):  # go through each trial on this page
            rec = parse_study(study)
            # Keep only INTERVENTIONAL trials (real treatment trials). Observational
            # studies just watch patients and don't have useful eligibility rules.
            if rec and rec.study_type == "INTERVENTIONAL":
                records.append(rec)
                if len(records) >= limit:
                    break  # we have enough, stop early

        # The API gives a "token" pointing to the next page. No token = last page.
        token = data.get("nextPageToken")
        if not token:
            break
        params["pageToken"] = token  # next loop will ask for the next page
        time.sleep(0.5)  # pause half a second to be polite to a free service

    return records


def main() -> None:
    """Runs when you start the file from the terminal."""
    # Define the options you can type after the command, with default values.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--condition", default="type 2 diabetes")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--out", default="../data/raw/trials.json")
    args = parser.parse_args()

    records = fetch_trials(args.condition, args.limit)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)  # create the folder if needed
    # model_dump() turns each TrialRecord into a plain dictionary, which
    # json.dumps writes out as text. indent=2 makes the file readable.
    out.write_text(json.dumps([r.model_dump() for r in records], indent=2))
    print(f"Saved {len(records)} trials to {out}")


# This line means: only run main() when the file is started directly,
# not when another file imports it.
if __name__ == "__main__":
    main()
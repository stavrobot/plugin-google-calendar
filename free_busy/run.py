#!/usr/bin/env -S uv run
# /// script
# dependencies = ["requests"]
# ///

import json
import sys

import requests

# The tool's CWD is free_busy/, so appending ".." makes the sibling shared/ package importable.
sys.path.append("..")

from shared.auth import get_calendar_headers, load_config

FREE_BUSY_URL = "https://www.googleapis.com/calendar/v3/freeBusy"


def parse_calendars(calendars: str) -> list[str]:
    # Same split/strip style as attendees, but de-duplicated (order kept) because the
    # result is keyed by calendar ID.
    ids = list(dict.fromkeys(c.strip() for c in calendars.split(",") if c.strip()))
    if not ids:
        raise ValueError("calendars must contain at least one calendar ID.")
    return ids


def fetch_free_busy(calendar_ids: list[str], time_min: str, time_max: str) -> dict:
    config = load_config()
    headers = get_calendar_headers(config)

    response = requests.post(
        FREE_BUSY_URL,
        headers=headers,
        json={
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": calendar_id} for calendar_id in calendar_ids],
        },
    )
    response.raise_for_status()
    return response.json().get("calendars", {})


def format_calendar(entry: dict | None) -> dict:
    # Google reports per-calendar problems (notFound, no access, ...) inside a 200 response.
    # Surface them as reason strings and leave the other calendars unaffected.
    if entry is None:
        return {"errors": ["missing_from_response"]}
    result: dict = {"busy": [{"start": b["start"], "end": b["end"]} for b in entry.get("busy", [])]}
    errors = [error.get("reason", "unknown") for error in entry.get("errors", [])]
    if errors:
        result["errors"] = errors
    return result


def main() -> None:
    params = json.load(sys.stdin)
    calendar_ids = parse_calendars(params["calendars"])

    found = fetch_free_busy(calendar_ids, params["time_min"], params["time_max"])
    formatted = {calendar_id: format_calendar(found.get(calendar_id)) for calendar_id in calendar_ids}

    json.dump({"calendars": formatted}, sys.stdout)


main()

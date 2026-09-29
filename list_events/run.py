#!/usr/bin/env -S uv run
# /// script
# dependencies = ["requests"]
# ///

import json
import sys
from datetime import datetime, timezone

import requests

# The tool's CWD is list_events/, so appending ".." makes the sibling shared/ package importable.
sys.path.append("..")

from shared.auth import events_url, get_calendar_headers, get_calendar_id, load_config


def fetch_events(
    max_results: int,
    calendar_id: str | None,
    time_min: str | None,
    time_max: str | None,
    query: str | None,
) -> list[dict]:
    config = load_config()
    headers = get_calendar_headers(config)
    calendar_id = get_calendar_id(config, calendar_id)

    request_params = {
        "timeMin": time_min or datetime.now(timezone.utc).isoformat(),
        "maxResults": max_results,
        # Expand recurring events into individual instances so they appear as discrete entries.
        "singleEvents": "true",
        "orderBy": "startTime",
    }
    if time_max:
        request_params["timeMax"] = time_max
    if query:
        request_params["q"] = query

    response = requests.get(
        events_url(calendar_id),
        headers=headers,
        params=request_params,
    )
    response.raise_for_status()
    return response.json().get("items", [])


def format_event(event: dict) -> dict:
    return {
        "id": event.get("id"),
        "title": event.get("summary"),
        # All-day events use "date" instead of "dateTime".
        "start": event["start"].get("dateTime") or event["start"].get("date"),
        "end": event["end"].get("dateTime") or event["end"].get("date"),
        "description": event.get("description"),
        "location": event.get("location"),
        "attendees": [attendee["email"] for attendee in event.get("attendees", [])],
    }


def main() -> None:
    params = json.load(sys.stdin)
    max_results = params.get("max_results", 10)

    events = fetch_events(
        max_results,
        params.get("calendar_id"),
        params.get("time_min"),
        params.get("time_max"),
        params.get("query"),
    )
    formatted = [format_event(event) for event in events]

    json.dump({"events": formatted}, sys.stdout)


main()

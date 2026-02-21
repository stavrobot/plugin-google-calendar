#!/usr/bin/env -S uv run
# /// script
# dependencies = ["requests"]
# ///

import json
import sys

import requests

# The tool's CWD is update_event/, so appending ".." makes the sibling shared/ package importable.
sys.path.append("..")

from shared.auth import get_calendar_headers, get_calendar_id, load_config


def build_time_field(value: str) -> dict[str, str]:
    # The Google Calendar API distinguishes all-day events (date) from timed events (dateTime)
    # by which field is present in the start/end object.
    if "T" in value:
        return {"dateTime": value}
    return {"date": value}


def format_event(event: dict) -> dict:
    return {
        "id": event.get("id"),
        "title": event.get("summary"),
        # All-day events use "date" instead of "dateTime".
        "start": event["start"].get("dateTime") or event["start"].get("date"),
        "end": event["end"].get("dateTime") or event["end"].get("date"),
        "description": event.get("description"),
    }


def update_event(event_id: str, params: dict) -> dict:
    config = load_config()
    headers = get_calendar_headers(config)
    calendar_id = get_calendar_id(config)

    # PATCH sends only the fields to change; omitting a field leaves it unchanged on the server.
    body: dict = {}

    if "title" in params:
        body["summary"] = params["title"]
    if "start" in params:
        body["start"] = build_time_field(params["start"])
    if "end" in params:
        body["end"] = build_time_field(params["end"])
    if "description" in params:
        body["description"] = params["description"]

    response = requests.patch(
        f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}",
        headers=headers,
        json=body,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    params = json.load(sys.stdin)
    event_id = params["event_id"]

    # Pass the full params dict so update_event can check which optional fields were provided.
    event = update_event(event_id, params)
    json.dump({"event": format_event(event)}, sys.stdout)


main()

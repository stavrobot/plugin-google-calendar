#!/usr/bin/env -S uv run
# /// script
# dependencies = ["requests"]
# ///

import json
import sys

import requests

# The tool's CWD is create_event/, so appending ".." makes the sibling shared/ package importable.
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


def create_event(title: str, start: str, end: str, description: str | None) -> dict:
    config = load_config()
    headers = get_calendar_headers(config)
    calendar_id = get_calendar_id(config)

    body: dict = {
        "summary": title,
        "start": build_time_field(start),
        "end": build_time_field(end),
    }

    # Only include description when provided; omitting it avoids sending a null field
    # that would overwrite an existing description on a subsequent update.
    if description is not None:
        body["description"] = description

    response = requests.post(
        f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events",
        headers=headers,
        json=body,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    params = json.load(sys.stdin)
    title = params["title"]
    start = params["start"]
    end = params["end"]
    description = params.get("description")

    event = create_event(title, start, end, description)
    json.dump({"event": format_event(event)}, sys.stdout)


main()

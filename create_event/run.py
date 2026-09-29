#!/usr/bin/env -S uv run
# /// script
# dependencies = ["requests"]
# ///

import json
import sys

import requests

# The tool's CWD is create_event/, so appending ".." makes the sibling shared/ package importable.
sys.path.append("..")

from shared.auth import events_url, get_calendar_headers, get_calendar_id, load_config


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
        "location": event.get("location"),
        "attendees": [a["email"] for a in event.get("attendees", [])],
    }


def parse_attendees(attendees: str) -> list[dict[str, str]]:
    # An empty string is almost certainly a caller mistake; "none" is the explicit
    # signal to clear attendees, so we surface a helpful error rather than silently
    # treating "" the same as "none".
    if attendees == "":
        raise ValueError('To remove all attendees, pass "none" instead of an empty string.')
    if attendees == "none":
        return []
    return [{"email": email.strip()} for email in attendees.split(",") if email.strip()]


def create_event(
    title: str,
    start: str,
    end: str,
    description: str | None,
    location: str | None,
    attendees: str | None,
    calendar_id: str | None,
) -> dict:
    config = load_config()
    headers = get_calendar_headers(config)
    calendar_id = get_calendar_id(config, calendar_id)

    body: dict = {
        "summary": title,
        "start": build_time_field(start),
        "end": build_time_field(end),
    }

    # Only include optional fields when provided; omitting them avoids sending null
    # fields that would overwrite existing values on a subsequent update.
    if description is not None:
        body["description"] = description
    if location is not None:
        body["location"] = location
    if attendees is not None:
        body["attendees"] = parse_attendees(attendees)

    response = requests.post(
        events_url(calendar_id),
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
    location = params.get("location")
    attendees = params.get("attendees")
    calendar_id = params.get("calendar_id")

    event = create_event(title, start, end, description, location, attendees, calendar_id)
    json.dump({"event": format_event(event)}, sys.stdout)


main()

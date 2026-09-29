#!/usr/bin/env -S uv run
# /// script
# dependencies = ["requests"]
# ///

import json
import sys

import requests

# The tool's CWD is list_calendars/, so appending ".." makes the sibling shared/ package importable.
sys.path.append("..")

from shared.auth import get_calendar_headers, load_config

CALENDAR_LIST_URL = "https://www.googleapis.com/calendar/v3/users/me/calendarList"


def fetch_calendars() -> list[dict]:
    config = load_config()
    headers = get_calendar_headers(config)

    calendars: list[dict] = []
    page_token: str | None = None
    while True:
        request_params = {"pageToken": page_token} if page_token else {}
        response = requests.get(CALENDAR_LIST_URL, headers=headers, params=request_params)
        response.raise_for_status()
        body = response.json()
        calendars.extend(body.get("items", []))
        page_token = body.get("nextPageToken")
        if not page_token:
            return calendars


def format_calendar(calendar: dict) -> dict:
    return {
        "id": calendar.get("id"),
        # summaryOverride is the user's own name for the calendar, so it wins over the original title.
        "name": calendar.get("summaryOverride") or calendar.get("summary"),
        "access_role": calendar.get("accessRole"),
        "primary": calendar.get("primary", False),
    }


def main() -> None:
    # This tool takes no parameters. Drain stdin so the runner's write always completes.
    sys.stdin.read()

    calendars = [format_calendar(calendar) for calendar in fetch_calendars()]

    json.dump({"calendars": calendars}, sys.stdout)


main()

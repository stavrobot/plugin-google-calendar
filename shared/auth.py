import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests


def load_config() -> dict[str, Any]:
    # config.json sits at the bundle root; tools run one level below it.
    return json.loads(Path("../config.json").read_text())


def get_access_token(config: dict[str, Any]) -> str:
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "refresh_token": config["refresh_token"],
            "grant_type": "refresh_token",
        },
    )
    response.raise_for_status()
    return response.json()["access_token"]


def get_calendar_headers(config: dict[str, Any]) -> dict[str, str]:
    token = get_access_token(config)
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def get_calendar_id(config: dict[str, Any], calendar_id: str | None = None) -> str:
    # An explicit calendar_id wins over the configured default. An empty string is rejected rather
    # than treated as omitted, so a bad target never silently writes to the default calendar.
    if calendar_id is None:
        return config["calendar_id"]
    if not calendar_id.strip():
        raise ValueError("calendar_id must not be empty; omit it to use the configured calendar.")
    return calendar_id


def events_url(calendar_id: str, event_id: str | None = None) -> str:
    # Calendar and event IDs can contain characters that are special in URLs (e.g. "#" in
    # holiday calendar IDs, "@" in emails), so every path segment must be fully encoded.
    url = f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar_id, safe='')}/events"
    if event_id is not None:
        url += f"/{quote(event_id, safe='')}"
    return url

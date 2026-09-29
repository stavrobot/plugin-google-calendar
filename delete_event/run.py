#!/usr/bin/env -S uv run
# /// script
# dependencies = ["requests"]
# ///

import json
import sys

import requests

# The tool's CWD is delete_event/, so appending ".." makes the sibling shared/ package importable.
sys.path.append("..")

from shared.auth import events_url, get_calendar_headers, get_calendar_id, load_config


def delete_event(event_id: str, calendar_id: str | None) -> None:
    config = load_config()
    headers = get_calendar_headers(config)
    calendar_id = get_calendar_id(config, calendar_id)

    response = requests.delete(
        events_url(calendar_id, event_id),
        headers=headers,
    )
    response.raise_for_status()


def main() -> None:
    params = json.load(sys.stdin)
    event_id = params["event_id"]

    delete_event(event_id, params.get("calendar_id"))
    json.dump({"deleted": True}, sys.stdout)


main()

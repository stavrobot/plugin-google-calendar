#!/usr/bin/env -S uv run
# /// script
# dependencies = ["requests"]
# ///

import json
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

# The tool's CWD is my_free_busy/, so appending ".." makes the sibling shared/ package importable.
sys.path.append("..")

from shared.auth import events_url, get_calendar_headers, load_config

MAX_RANGE = timedelta(days=31)
PAGE_SIZE = 2500
DEFAULT_LEAVE_MIN_HOURS = 8
DEFAULT_IGNORED_TITLES = "I don't work Mondays,AL,On AL"
# U+2019 RIGHT SINGLE QUOTATION MARK, normalised to a plain apostrophe before matching.
CURLY_APOSTROPHE = "\u2019"


class InputError(Exception):
    """A caller mistake. Its message is fixed and safe to show; it never includes event data."""


def parse_time(value: object, name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise InputError(
            f"{name} is required, as an RFC 3339 timestamp with a timezone (e.g. 2025-06-15T00:00:00Z)."
        )
    text = value.strip()
    # fromisoformat handles "Z" on recent Pythons, but normalise it so the tool works on older ones too.
    if text[-1] in ("Z", "z"):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        raise InputError(
            f"{name} must be an RFC 3339 timestamp with a timezone (e.g. 2025-06-15T00:00:00Z)."
        )
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise InputError(f"{name} must include a timezone (e.g. 2025-06-15T00:00:00Z).")
    return moment


def validate_range(time_min: datetime, time_max: datetime) -> None:
    if time_max <= time_min:
        raise InputError("time_max must be after time_min.")
    if time_max - time_min > MAX_RANGE:
        raise InputError("The time range must not exceed 31 days.")


def normalize_title(title: object) -> str:
    # Case-insensitive exact matching, tolerant of the smart apostrophe editors like to insert.
    return str(title).strip().replace(CURLY_APOSTROPHE, "'").casefold()


def parse_ignored_titles(raw: object) -> set[str]:
    return {normalize_title(part) for part in str(raw).split(",") if part.strip()}


def parse_event_time(field: dict, calendar_tz: str) -> datetime:
    date_time = field.get("dateTime")
    if date_time:
        return datetime.fromisoformat(date_time.replace("Z", "+00:00"))
    # All-day events use an exclusive "date"; anchor them to midnight in the calendar's timezone.
    day = datetime.fromisoformat(field["date"]).date()
    return datetime(day.year, day.month, day.day, tzinfo=ZoneInfo(calendar_tz))


def event_bounds(event: dict, calendar_tz: str) -> tuple[datetime, datetime]:
    # Normalise both bounds to UTC so subtraction measures elapsed time. Two datetimes sharing the
    # same ZoneInfo subtract as wall-clock time, so an all-day event across a DST change would look
    # like 24h when it is really 23h (or 25h).
    return (
        parse_event_time(event["start"], calendar_tz).astimezone(timezone.utc),
        parse_event_time(event["end"], calendar_tz).astimezone(timezone.utc),
    )


def is_off_window(
    event: dict,
    start: datetime,
    end: datetime,
    leave_min_hours: float,
    ignored_titles: set[str],
) -> bool:
    if event.get("eventType") == "outOfOffice" and end - start >= timedelta(hours=leave_min_hours):
        return True
    summary = event.get("summary")
    return summary is not None and normalize_title(summary) in ignored_titles


def should_skip(event: dict) -> bool:
    if event.get("eventType") in ("workingLocation", "birthday"):
        return True
    return event.get("transparency") == "transparent"


def self_response_status(event: dict) -> str | None:
    for attendee in event.get("attendees", []):
        if attendee.get("self") is True:
            return attendee.get("responseStatus")
    return None


def subtract_windows(
    start: datetime, end: datetime, off_windows: list[tuple[datetime, datetime]]
) -> list[tuple[datetime, datetime]]:
    segments = [(start, end)]
    for window_start, window_end in off_windows:
        remaining = []
        for segment_start, segment_end in segments:
            if window_end <= segment_start or window_start >= segment_end:
                remaining.append((segment_start, segment_end))
                continue
            if segment_start < window_start:
                remaining.append((segment_start, window_start))
            if segment_end > window_end:
                remaining.append((window_end, segment_end))
        segments = remaining
    return segments


def fetch_events(config: dict, time_min: datetime, time_max: datetime) -> tuple[list[dict], str]:
    headers = get_calendar_headers(config)
    calendar_id = config["calendar_id"]

    events: list[dict] = []
    calendar_tz = "UTC"
    page_token: str | None = None
    while True:
        request_params = {
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "singleEvents": "true",
            "maxResults": PAGE_SIZE,
        }
        if page_token:
            request_params["pageToken"] = page_token

        response = requests.get(events_url(calendar_id), headers=headers, params=request_params)
        response.raise_for_status()
        body = response.json()
        if body.get("timeZone"):
            calendar_tz = body["timeZone"]
        events.extend(body.get("items", []))
        page_token = body.get("nextPageToken")
        if not page_token:
            return events, calendar_tz


def collect_busy(time_min: datetime, time_max: datetime) -> list[tuple[datetime, datetime]]:
    config = load_config()
    leave_min_hours = float(config.get("leave_min_hours", DEFAULT_LEAVE_MIN_HOURS))
    ignored_titles = parse_ignored_titles(config.get("ignored_titles", DEFAULT_IGNORED_TITLES))

    events, calendar_tz = fetch_events(config, time_min, time_max)
    # Cancelled events are dropped before anything else: a cancelled leave block must not free time,
    # and cancelled instances can arrive without start/end.
    bounded = [
        (event, *event_bounds(event, calendar_tz))
        for event in events
        if event.get("status") != "cancelled"
    ]

    # Off windows are gathered up front so a later event can subtract from an earlier one.
    off_windows = [
        (start, end)
        for event, start, end in bounded
        if is_off_window(event, start, end, leave_min_hours, ignored_titles)
    ]

    busy: list[tuple[datetime, datetime]] = []
    for event, start, end in bounded:
        if is_off_window(event, start, end, leave_min_hours, ignored_titles):
            continue
        if should_skip(event):
            continue
        status = self_response_status(event)
        if status is None or status == "accepted":
            busy.append((start, end))
        else:
            busy.extend(subtract_windows(start, end, off_windows))
    return busy


def to_utc_string(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_busy(
    intervals: list[tuple[datetime, datetime]], time_min: datetime, time_max: datetime
) -> list[dict[str, str]]:
    clipped = []
    for start, end in intervals:
        clipped_start = max(start, time_min)
        clipped_end = min(end, time_max)
        if clipped_start < clipped_end:
            clipped.append((clipped_start, clipped_end))
    clipped.sort(key=lambda interval: interval[0])

    merged: list[tuple[datetime, datetime]] = []
    for start, end in clipped:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    return [{"start": to_utc_string(start), "end": to_utc_string(end)} for start, end in merged]


def main() -> None:
    try:
        params = json.load(sys.stdin)
        if not isinstance(params, dict):
            raise InputError("Input must be a JSON object with time_min and time_max.")
        time_min = parse_time(params.get("time_min"), "time_min")
        time_max = parse_time(params.get("time_max"), "time_max")
        validate_range(time_min, time_max)
        busy = format_busy(collect_busy(time_min, time_max), time_min, time_max)
    except requests.HTTPError as error:
        # requests' HTTPError message contains the request URL (i.e. the calendar ID/email), so it
        # must never reach stderr.
        status = getattr(getattr(error, "response", None), "status_code", None)
        print(f"Calendar API error: HTTP {status}", file=sys.stderr)
        sys.exit(1)
    except InputError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    except Exception as error:  # noqa: BLE001 - fail closed, never leak the exception's contents
        print(type(error).__name__, file=sys.stderr)
        sys.exit(1)

    json.dump({"busy": busy}, sys.stdout)


if __name__ == "__main__":
    main()

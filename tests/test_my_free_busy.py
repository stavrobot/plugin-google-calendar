"""Tests for the my_free_busy tool.

HTTP is faked at the requests module boundary, so these tests need no network access or
credentials. The tool is loaded from its file path (tools are standalone scripts, not an
importable package)."""

import importlib.util
import io
import json
import sys
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

_spec = importlib.util.spec_from_file_location(
    "my_free_busy_run", REPO_ROOT / "my_free_busy" / "run.py"
)
run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run)


CONFIG = {
    "client_id": "client-id",
    "client_secret": "client-secret",
    "refresh_token": "refresh-token",
    "calendar_id": "primary",
}

RANGE = {"time_min": "2025-06-16T00:00:00Z", "time_max": "2025-06-19T00:00:00Z"}


class FakeResponse:
    def __init__(self, payload, status_code=200, url="", error_message=None):
        self.payload = payload
        self.status_code = status_code
        self.url = url
        self.error_message = error_message

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            # Mirror requests: the message carries the request URL (which includes the calendar ID).
            message = self.error_message or f"{self.status_code} Server Error: for url: {self.url}"
            raise requests.HTTPError(message, response=self)


class FakeHTTP:
    def __init__(self, pages=None, status=200, fail_on_call=None, error_message=None):
        self.pages = list(pages or [])
        self.status = status
        self.fail_on_call = fail_on_call
        self.error_message = error_message
        self.get_calls = []
        self.post_calls = []

    def post(self, url, **kwargs):
        self.post_calls.append(url)
        return FakeResponse({"access_token": "test-token"}, url=url)

    def get(self, url, headers=None, params=None):
        self.get_calls.append({"url": url, "headers": headers, "params": dict(params or {})})
        call_number = len(self.get_calls)
        should_fail = self.status >= 400
        if self.fail_on_call is not None:
            should_fail = call_number == self.fail_on_call
        if should_fail:
            code = self.status if self.status >= 400 else 500
            return FakeResponse(
                {}, status_code=code, url=url, error_message=self.error_message
            )
        if self.pages:
            return FakeResponse(self.pages.pop(0), url=url)
        return FakeResponse({"timeZone": "UTC", "items": []}, url=url)


def page(items, timezone="UTC", next_page_token=None):
    body = {"timeZone": timezone, "items": items}
    if next_page_token:
        body["nextPageToken"] = next_page_token
    return body


def event(summary, start, end, **extra):
    return {"summary": summary, "start": {"dateTime": start}, "end": {"dateTime": end}, **extra}


def all_day(summary, start_date, end_date, **extra):
    return {"summary": summary, "start": {"date": start_date}, "end": {"date": end_date}, **extra}


def ooo(start, end, summary="Leave", **extra):
    return event(summary, start, end, eventType="outOfOffice", **extra)


def meeting(start, end, response_status, summary="Meeting", self_attendee=True, **extra):
    attendees = [{"email": "me@example.com", "self": self_attendee, "responseStatus": response_status}]
    return event(summary, start, end, attendees=attendees, **extra)


def invoke(monkeypatch, capsys, params, pages=None, config=None, status=200, **fake_kwargs):
    fake = FakeHTTP(pages, status=status, **fake_kwargs)
    settings = {**CONFIG, **(config or {})}
    monkeypatch.setattr(run, "load_config", lambda: dict(settings))
    monkeypatch.setattr(run.requests, "get", fake.get)
    monkeypatch.setattr(run.requests, "post", fake.post)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(params)))

    code = 0
    try:
        run.main()
    except SystemExit as exc:
        code = exc.code
    captured = capsys.readouterr()
    return code, captured.out, captured.err, fake


def busy_blocks(monkeypatch, capsys, pages, params=None, **kwargs):
    code, out, err, fake = invoke(monkeypatch, capsys, params or RANGE, pages, **kwargs)
    assert code == 0, err
    return json.loads(out)["busy"], fake


# --- output shape and calendar restriction -------------------------------------------------


def test_output_only_has_start_and_end_keys(monkeypatch, capsys):
    items = [
        event("Standup", "2025-06-16T09:00:00Z", "2025-06-16T09:30:00Z"),
        event("Review", "2025-06-16T11:00:00Z", "2025-06-16T12:00:00Z"),
    ]
    busy, _ = busy_blocks(monkeypatch, capsys, [page(items)])

    assert len(busy) == 2
    for block in busy:
        assert set(block) == {"start", "end"}


def test_targets_configured_calendar_and_ignores_caller_calendar(monkeypatch, capsys):
    params = {
        **RANGE,
        "calendar_id": "attacker@example.com",
        "calendars": "attacker@example.com",
    }
    _, fake = busy_blocks(
        monkeypatch,
        capsys,
        [page([event("Standup", "2025-06-16T09:00:00Z", "2025-06-16T09:30:00Z")])],
        params=params,
    )

    assert len(fake.get_calls) == 1
    url = fake.get_calls[0]["url"]
    assert url == "https://www.googleapis.com/calendar/v3/calendars/primary/events"
    assert "attacker" not in url

    sent = fake.get_calls[0]["params"]
    assert sent["singleEvents"] == "true"
    assert int(sent["maxResults"]) == 2500


# --- leak prevention -----------------------------------------------------------------------


def test_event_markers_never_appear_in_output(monkeypatch, capsys):
    marker = "SECRET-MARKER-1a2b3c"
    items = [
        event(
            f"{marker} title",
            "2025-06-16T09:00:00Z",
            "2025-06-16T10:00:00Z",
            description=f"{marker} description",
        )
    ]
    code, out, err, _ = invoke(monkeypatch, capsys, RANGE, [page(items)])

    assert code == 0
    assert marker not in out
    assert marker not in err


def test_calendar_email_never_appears_in_api_error(monkeypatch, capsys):
    config = {"calendar_id": "secret-calendar@example.com"}
    code, out, err, _ = invoke(monkeypatch, capsys, RANGE, status=500, config=config)

    assert code == 1
    assert out == ""
    assert err == "Calendar API error: HTTP 500\n"
    assert "secret-calendar" not in err
    assert "Traceback" not in err


def test_api_error_fails_instead_of_returning_empty_list(monkeypatch, capsys):
    code, out, err, _ = invoke(monkeypatch, capsys, RANGE, status=403)

    assert code == 1
    assert out == ""
    assert err.strip() == "Calendar API error: HTTP 403"


def test_unexpected_exception_is_sanitised(monkeypatch, capsys):
    marker = "MALFORMED-MARKER-9z"
    items = [{"summary": "X", "start": {"dateTime": marker}, "end": {"dateTime": marker}}]
    code, out, err, _ = invoke(monkeypatch, capsys, RANGE, [page(items)])

    assert code == 1
    assert out == ""
    assert err.strip() == "ValueError"
    assert marker not in err
    assert "Traceback" not in err


def test_api_error_on_second_page_fails_without_partial_output(monkeypatch, capsys):
    pages = [page([event("A", "2025-06-16T09:00:00Z", "2025-06-16T10:00:00Z")], next_page_token="tok")]
    code, out, err, fake = invoke(monkeypatch, capsys, RANGE, pages, status=500, fail_on_call=2)

    assert code == 1
    assert out == ""
    assert err.strip() == "Calendar API error: HTTP 500"
    assert len(fake.get_calls) == 2


def test_http_error_message_marker_is_not_leaked(monkeypatch, capsys):
    marker = "TITLE-MARKER-777"
    code, out, err, _ = invoke(
        monkeypatch, capsys, RANGE, status=500, error_message=f"500 Server Error: {marker}"
    )

    assert code == 1
    assert out == ""
    assert marker not in err
    assert err.strip() == "Calendar API error: HTTP 500"


# --- no events -----------------------------------------------------------------------------


def test_day_with_no_events_has_no_busy_blocks(monkeypatch, capsys):
    busy, _ = busy_blocks(monkeypatch, capsys, [page([])])

    assert busy == []


# --- off windows ---------------------------------------------------------------------------


def test_eight_hour_ooo_is_free_but_short_ooo_is_busy(monkeypatch, capsys):
    items = [
        ooo("2025-06-16T09:00:00Z", "2025-06-16T17:00:00Z"),
        ooo("2025-06-17T10:00:00Z", "2025-06-17T11:30:00Z"),
    ]
    busy, _ = busy_blocks(monkeypatch, capsys, [page(items)])

    assert busy == [{"start": "2025-06-17T10:00:00Z", "end": "2025-06-17T11:30:00Z"}]


def test_ignored_titles_are_free_including_curly_apostrophe(monkeypatch, capsys):
    items = [
        event("AL", "2025-06-16T09:00:00Z", "2025-06-16T10:00:00Z"),
        event("I don\u2019t work Mondays", "2025-06-17T09:00:00Z", "2025-06-17T10:00:00Z"),
        # Not an exact match, so it stays busy.
        event("AL planning", "2025-06-18T09:00:00Z", "2025-06-18T10:00:00Z"),
    ]
    busy, _ = busy_blocks(monkeypatch, capsys, [page(items)])

    assert busy == [{"start": "2025-06-18T09:00:00Z", "end": "2025-06-18T10:00:00Z"}]


def test_transparent_working_location_birthday_and_cancelled_are_free(monkeypatch, capsys):
    items = [
        event("Busy?", "2025-06-16T09:00:00Z", "2025-06-16T10:00:00Z", transparency="transparent"),
        event("Office", "2025-06-16T10:00:00Z", "2025-06-16T11:00:00Z", eventType="workingLocation"),
        event("Birthday", "2025-06-16T11:00:00Z", "2025-06-16T12:00:00Z", eventType="birthday"),
        event("Gone", "2025-06-16T13:00:00Z", "2025-06-16T14:00:00Z", status="cancelled"),
    ]
    busy, _ = busy_blocks(monkeypatch, capsys, [page(items)])

    assert busy == []


def test_short_ooo_is_busy_even_with_attendees(monkeypatch, capsys):
    # 1.5h out-of-office is below the threshold, so it is a normal (busy) interval.
    items = [ooo("2025-06-16T10:00:00Z", "2025-06-16T11:30:00Z")]
    busy, _ = busy_blocks(monkeypatch, capsys, [page(items)])

    assert busy == [{"start": "2025-06-16T10:00:00Z", "end": "2025-06-16T11:30:00Z"}]


# --- self attendee response statuses -------------------------------------------------------


def test_declined_tentative_and_needs_action_meetings_are_busy_on_a_normal_day(monkeypatch, capsys):
    items = [
        meeting("2025-06-16T09:00:00Z", "2025-06-16T09:30:00Z", "declined"),
        meeting("2025-06-16T10:00:00Z", "2025-06-16T10:30:00Z", "tentative"),
        meeting("2025-06-16T11:00:00Z", "2025-06-16T11:30:00Z", "needsAction"),
    ]
    busy, _ = busy_blocks(monkeypatch, capsys, [page(items)])

    assert busy == [
        {"start": "2025-06-16T09:00:00Z", "end": "2025-06-16T09:30:00Z"},
        {"start": "2025-06-16T10:00:00Z", "end": "2025-06-16T10:30:00Z"},
        {"start": "2025-06-16T11:00:00Z", "end": "2025-06-16T11:30:00Z"},
    ]


def test_declined_meeting_inside_leave_block_is_free(monkeypatch, capsys):
    items = [
        ooo("2025-06-16T09:00:00Z", "2025-06-16T17:00:00Z"),
        meeting("2025-06-16T10:00:00Z", "2025-06-16T11:00:00Z", "declined"),
    ]
    busy, _ = busy_blocks(monkeypatch, capsys, [page(items)])

    assert busy == []


def test_cancelled_leave_block_does_not_free_time(monkeypatch, capsys):
    items = [
        ooo("2025-06-16T09:00:00Z", "2025-06-16T17:00:00Z", status="cancelled"),
        meeting("2025-06-16T10:00:00Z", "2025-06-16T11:00:00Z", "declined"),
        # Cancelled instances can arrive with no start/end; they must not crash the tool.
        {"id": "x", "status": "cancelled"},
    ]
    busy, _ = busy_blocks(monkeypatch, capsys, [page(items)])

    assert busy == [{"start": "2025-06-16T10:00:00Z", "end": "2025-06-16T11:00:00Z"}]


def test_declined_meeting_inside_ignored_title_block_is_free(monkeypatch, capsys):
    items = [
        event("AL", "2025-06-16T09:00:00Z", "2025-06-16T17:00:00Z"),
        meeting("2025-06-16T10:00:00Z", "2025-06-16T11:00:00Z", "tentative"),
    ]
    busy, _ = busy_blocks(monkeypatch, capsys, [page(items)])

    assert busy == []


def test_declined_meeting_partly_overlapping_leave_is_busy_only_outside(monkeypatch, capsys):
    items = [
        ooo("2025-06-16T09:00:00Z", "2025-06-16T17:00:00Z"),
        meeting("2025-06-16T16:00:00Z", "2025-06-16T18:00:00Z", "declined"),
    ]
    busy, _ = busy_blocks(monkeypatch, capsys, [page(items)])

    assert busy == [{"start": "2025-06-16T17:00:00Z", "end": "2025-06-16T18:00:00Z"}]


def test_accepted_meeting_inside_leave_block_is_busy(monkeypatch, capsys):
    items = [
        ooo("2025-06-16T09:00:00Z", "2025-06-16T17:00:00Z"),
        meeting("2025-06-16T10:00:00Z", "2025-06-16T11:00:00Z", "accepted"),
    ]
    busy, _ = busy_blocks(monkeypatch, capsys, [page(items)])

    assert busy == [{"start": "2025-06-16T10:00:00Z", "end": "2025-06-16T11:00:00Z"}]


def test_accepted_meeting_inside_ignored_title_block_is_busy(monkeypatch, capsys):
    items = [
        event("AL", "2025-06-16T09:00:00Z", "2025-06-16T17:00:00Z"),
        meeting("2025-06-16T10:00:00Z", "2025-06-16T11:00:00Z", "accepted"),
    ]
    busy, _ = busy_blocks(monkeypatch, capsys, [page(items)])

    assert busy == [{"start": "2025-06-16T10:00:00Z", "end": "2025-06-16T11:00:00Z"}]


# --- rule 4 and timezone handling ----------------------------------------------------------


def test_own_event_without_attendees_is_busy(monkeypatch, capsys):
    items = [event("Focus", "2025-06-16T09:00:00Z", "2025-06-16T10:00:00Z")]
    busy, _ = busy_blocks(monkeypatch, capsys, [page(items)])

    assert busy == [{"start": "2025-06-16T09:00:00Z", "end": "2025-06-16T10:00:00Z"}]


def test_attendee_event_without_self_is_busy(monkeypatch, capsys):
    items = [meeting("2025-06-16T09:00:00Z", "2025-06-16T10:00:00Z", "declined", self_attendee=False)]
    busy, _ = busy_blocks(monkeypatch, capsys, [page(items)])

    assert busy == [{"start": "2025-06-16T09:00:00Z", "end": "2025-06-16T10:00:00Z"}]


def test_all_day_event_is_busy_and_uses_response_timezone(monkeypatch, capsys):
    params = {"time_min": "2025-06-15T00:00:00Z", "time_max": "2025-06-18T00:00:00Z"}
    items = [all_day("Holiday", "2025-06-16", "2025-06-17")]
    busy, _ = busy_blocks(monkeypatch, capsys, [page(items, timezone="Europe/Athens")], params=params)

    # Midnight in Athens (UTC+3 in June) is 21:00 UTC the previous day.
    assert busy == [{"start": "2025-06-15T21:00:00Z", "end": "2025-06-16T21:00:00Z"}]


def test_all_day_ooo_spanning_dst_uses_elapsed_time_not_wall_clock(monkeypatch, capsys):
    # Europe/Athens springs forward on 2025-03-30, so this all-day OOO lasts 23h, not 24h, and must
    # not reach the 24h leave threshold (it stays busy).
    params = {"time_min": "2025-03-29T00:00:00Z", "time_max": "2025-04-01T00:00:00Z"}
    items = [all_day("Leave", "2025-03-30", "2025-03-31", eventType="outOfOffice")]
    busy, _ = busy_blocks(
        monkeypatch,
        capsys,
        [page(items, timezone="Europe/Athens")],
        params=params,
        config={"leave_min_hours": 24},
    )

    assert busy == [{"start": "2025-03-29T22:00:00Z", "end": "2025-03-30T21:00:00Z"}]


def test_result_is_clipped_merged_and_sorted(monkeypatch, capsys):
    items = [
        event("B", "2025-06-16T11:00:00Z", "2025-06-16T13:00:00Z"),
        event("A", "2025-06-16T09:00:00Z", "2025-06-16T10:00:00Z"),
        # Overlaps A? no, but overlaps B's start; also adjacent to A.
        event("C", "2025-06-16T10:00:00Z", "2025-06-16T11:30:00Z"),
    ]
    busy, _ = busy_blocks(monkeypatch, capsys, [page(items)])

    assert busy == [{"start": "2025-06-16T09:00:00Z", "end": "2025-06-16T13:00:00Z"}]


def test_paging_follows_next_page_token(monkeypatch, capsys):
    pages = [
        page([event("A", "2025-06-16T09:00:00Z", "2025-06-16T10:00:00Z")], next_page_token="tok"),
        page([event("B", "2025-06-17T09:00:00Z", "2025-06-17T10:00:00Z")]),
    ]
    busy, fake = busy_blocks(monkeypatch, capsys, pages)

    assert len(fake.get_calls) == 2
    assert fake.get_calls[0]["params"].get("pageToken") is None
    assert fake.get_calls[1]["params"]["pageToken"] == "tok"
    assert busy == [
        {"start": "2025-06-16T09:00:00Z", "end": "2025-06-16T10:00:00Z"},
        {"start": "2025-06-17T09:00:00Z", "end": "2025-06-17T10:00:00Z"},
    ]


# --- input validation ----------------------------------------------------------------------


def test_rejects_naive_timestamp(monkeypatch, capsys):
    params = {"time_min": "2025-06-16T00:00:00", "time_max": "2025-06-17T00:00:00Z"}
    code, out, err, fake = invoke(monkeypatch, capsys, params)

    assert code == 1
    assert out == ""
    assert "time_min" in err
    assert fake.get_calls == []


def test_rejects_missing_or_backwards_range(monkeypatch, capsys):
    code, _, _, _ = invoke(monkeypatch, capsys, {"time_min": "2025-06-16T00:00:00Z"})
    assert code == 1

    params = {"time_min": "2025-06-17T00:00:00Z", "time_max": "2025-06-16T00:00:00Z"}
    code, _, _, _ = invoke(monkeypatch, capsys, params)
    assert code == 1


def test_rejects_range_over_31_days(monkeypatch, capsys):
    params = {"time_min": "2025-01-01T00:00:00Z", "time_max": "2025-03-01T00:00:00Z"}
    code, out, err, _ = invoke(monkeypatch, capsys, params)

    assert code == 1
    assert out == ""
    assert "31 days" in err

---
id: rep-evawz
status: closed
deps: []
links: []
created: 2026-10-12T18:31:44Z
type: task
priority: 2
assignee: Stavros Korokithakis
---
# Add my_free_busy tool restricted to the configured calendar

Ready for implementation.

Objective: new tool my_free_busy(time_min, time_max) that returns only {"busy": [{"start", "end"}]} for the plugin's configured calendar_id, with busy rules decided inside the plugin. It is granted to an agent that talks to third parties, so nothing about events may leak.

Scope: new my_free_busy/ (manifest.json + run.py, same structure as other tools); plugin manifest.json config; tests/test_my_free_busy.py (pytest, HTTP faked, no network); README tool table + short 'Development' section with test command: uv run --with pytest --with requests pytest.

Behaviour:
- No calendar parameter. Always use config calendar_id ("primary" works as-is in the events API). Ignore extra input keys (e.g. calendar_id/calendars).
- time_min/time_max required, RFC 3339 with timezone (reject naive), time_max > time_min, range <= 31 days.
- GET events list on the configured calendar: timeMin/timeMax, singleEvents=true, maxResults=2500, follow nextPageToken. Use the response timeZone to convert all-day (date) events to instants.
- Config (plugin manifest, required: false, defaults in code): leave_min_hours (default 8), ignored_titles (comma-separated, default "I don't work Mondays,AL,On AL").
- Title matching: case-insensitive (casefold) exact match after strip, with U+2019 ’ normalised to ' on both sides.

Rules (in order):
1. Off windows (not busy themselves): eventType outOfOffice with duration (end - start) >= leave_min_hours; or title matches ignored_titles.
2. Skip entirely: status cancelled; eventType workingLocation or birthday; transparency transparent.
3. Events with attendees that include an entry with self: true: responseStatus accepted -> busy always (even inside off windows). declined/tentative/needsAction -> busy minus overlap with off windows (subtract only the overlapping part).
4. Everything else is busy (own events without attendees, attendee events with no self entry, short OOO, all-day events), even inside off windows.
Output: clip to [time_min, time_max], merge, sort, UTC 'YYYY-MM-DDTHH:MM:SSZ'. Only start/end keys.

Must not leak: no titles, descriptions, attendees, IDs, calendar IDs/emails, event types, statuses or counts in output or errors. Stavrobot passes stdout/stderr of failed tools to the agent, and requests' HTTPError message contains the URL (with the calendar email). So main() must catch every exception, print one sanitised line to stderr (HTTP errors: 'Calendar API error: HTTP <code>'; other unexpected errors: type name only; own input-validation errors may keep their fixed messages), exit 1, no traceback. Never return an empty list on API error. run.py calls main() only under if __name__ == '__main__' so tests can import it.

Non-goals: no changes to free_busy or other tools; no working-hours logic; no shared/ changes beyond what's needed (none expected); no fix of URL leaks in other tools.

## Acceptance Criteria

Tests cover: output only has start/end keys; tool cannot target another calendar (request URL uses configured calendar even when calendar_id is passed); marker strings in titles/descriptions never appear in output or errors (including an API error path); 8h OOO is free while 1.5h OOO is busy; ignored-title (incl. curly apostrophe), transparent, workingLocation and birthday events are free; declined/tentative/needsAction meetings on a normal day are busy; same meetings inside a leave block or ignored-title block are free; such a meeting partly overlapping a leave block is busy only for the non-overlapping part; accepted meeting inside leave or ignored-title block is busy; a day with no events returns no busy blocks; API error causes failure, not an empty list.


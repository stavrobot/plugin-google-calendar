---
id: pgc-jlwrs
status: closed
deps: []
links: []
created: 2026-09-29T00:07:51Z
type: task
priority: 2
assignee: Stavros Korokithakis
---
# Add list_calendars tool

Ready for implementation.

Objective: let the model discover which calendars the user can access and their IDs.

Scope: new list_calendars/ directory (manifest.json + run.py), following the existing tool structure exactly; README tool table.

- Call GET https://www.googleapis.com/calendar/v3/users/me/calendarList. No parameters needed. Follow nextPageToken so the full list is returned (lists are small, but paging is part of this endpoint).
- For each calendar return: id, name (summary; prefer summaryOverride if set), access_role (accessRole: owner/writer/reader/freeBusyReader), primary (bool, default false).
- Manifest description should explain that access_role tells what the user can do on that calendar.

Non-goals: no filtering params, no subscribe/unsubscribe.


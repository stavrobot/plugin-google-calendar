---
id: pgc-ogztq
status: closed
deps: [pgc-ltmvn]
links: []
created: 2026-09-29T00:07:51Z
type: task
priority: 2
assignee: Stavros Korokithakis
---
# Add time_min, time_max and query params to list_events

Ready for implementation.

Objective: let list_events answer questions like 'what is on Alice's calendar next Tuesday' or 'find the dentist appointment'.

Scope: list_events/run.py, list_events/manifest.json, README tool table.

- time_min (optional, RFC 3339): maps to timeMin. Defaults to now (current behaviour).
- time_max (optional, RFC 3339): maps to timeMax. No default; omit from the request when not given.
- query (optional string): maps to Google's 'q' free-text search. Omit when not given.
- Keep max_results and its default of 10.

Non-goals: no paging, no multi-calendar listing.


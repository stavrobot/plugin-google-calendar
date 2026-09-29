---
id: pgc-ltmvn
status: closed
deps: []
links: []
created: 2026-09-29T00:07:51Z
type: task
priority: 2
assignee: Stavros Korokithakis
---
# Add optional calendar_id param to all event tools and URL-encode path IDs

Ready for implementation.

Objective: let list_events, create_event, update_event, delete_event operate on any calendar the user can access (shared/colleague calendars), not only config calendar_id.

Scope: shared/auth.py, the four tools' run.py and manifest.json, README tool table.

- Add optional 'calendar_id' parameter to all four tools. When omitted, fall back to config calendar_id (current behaviour must stay unchanged). Put the fallback logic in shared/ so the four tools do not duplicate it.
- URL-encode calendar ID and event ID in every request path (urllib.parse.quote with safe=''). Some calendar IDs contain '#' (e.g. holiday calendars), which currently breaks the URL.
- Manifest descriptions should tell the model that calendar_id is usually a person's email address, and that list_calendars returns available IDs.

Non-goals: no config/auth changes, no permission pre-checks (Google enforces them), no other new params.


---
id: pgc-oobax
status: closed
deps: []
links: []
created: 2026-09-29T00:07:51Z
type: task
priority: 2
assignee: Stavros Korokithakis
---
# Add free_busy tool

Ready for implementation.

Objective: let the model find busy/free time for several people, mainly Workspace colleagues whose details are not shared.

Scope: new free_busy/ directory (manifest.json + run.py), following the existing tool structure; README tool table.

- Params: calendars (required, comma-separated emails or calendar IDs, same split/strip style as attendees), time_min and time_max (both required, RFC 3339).
- Call POST https://www.googleapis.com/calendar/v3/freeBusy with timeMin, timeMax, items=[{id}].
- Output: one entry per requested calendar with its busy blocks (start/end). Google returns per-calendar 'errors' (e.g. notFound, no access) inside a 200 response; surface those per calendar and still return the others. Do not fail the whole call for a per-calendar error.

Non-goals: no computing of free slots (the model can do that), no groups expansion handling beyond what Google returns.


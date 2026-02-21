# google-calendar

A [Stavrobot](https://github.com/stavros-k/stavrobot) plugin that lets the assistant manage Google Calendar events.

## Installation

Ask Stavrobot to install https://github.com/stavrobot/plugin-google-calendar.git.

## Tools

| Tool | Description |
|------|-------------|
| `list_events` | List upcoming events. Accepts `max_results` (default: 10). |
| `create_event` | Create an event. Requires `title`, `start`, `end`; accepts optional `description`. |
| `update_event` | Update an existing event by `event_id`. All other fields are optional. |
| `delete_event` | Delete an event by `event_id`. |

Times use RFC 3339 format (e.g. `2025-06-15T10:00:00Z`). All-day events use a plain date (e.g. `2025-06-15`).

## Setup

### 1. Create a Google Cloud project

Go to <https://console.cloud.google.com/> and create a new project or select an existing one.

### 2. Enable the Google Calendar API

In the project, go to **APIs & Services > Library**, search for "Google Calendar API", and click **Enable**.

### 3. Create OAuth 2.0 credentials

Go to **APIs & Services > Credentials**, click **Create Credentials > OAuth client ID**, and choose application type **Desktop app**. Note the `client_id` and `client_secret`.

### 4. Obtain a refresh token

**Step 4a.** Open this URL in your browser (replace `CLIENT_ID`):

```
https://accounts.google.com/o/oauth2/v2/auth?client_id=CLIENT_ID&redirect_uri=urn:ietf:wg:oauth:2.0:oob&response_type=code&scope=https://www.googleapis.com/auth/calendar&access_type=offline&prompt=consent
```

After granting access, Google shows an authorization code.

**Step 4b.** Exchange the code for tokens:

```bash
curl -s -X POST https://oauth2.googleapis.com/token \
  -d client_id=CLIENT_ID \
  -d client_secret=CLIENT_SECRET \
  -d code=AUTH_CODE \
  -d grant_type=authorization_code \
  -d redirect_uri=urn:ietf:wg:oauth:2.0:oob
```

The response JSON contains a `refresh_token` field.

### 5. Create config.json

Create `config.json` at the plugin root (next to `manifest.json`):

```json
{
  "client_id": "your-client-id",
  "client_secret": "your-client-secret",
  "refresh_token": "your-refresh-token",
  "calendar_id": "primary"
}
```

Use `"primary"` for `calendar_id` to target your main calendar, or replace it with a specific calendar ID (visible in Google Calendar settings under each calendar's details).

## License

AGPL-3.0. See [LICENSE](LICENSE).

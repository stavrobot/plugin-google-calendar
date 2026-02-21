import json
from pathlib import Path
from typing import Any

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


def get_calendar_id(config: dict[str, Any]) -> str:
    return config["calendar_id"]

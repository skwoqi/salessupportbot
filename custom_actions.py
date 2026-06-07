from __future__ import annotations

import json
from pathlib import Path

ACTIONS_FILE = Path("custom_actions.json")


def get_actions() -> list[dict[str, str]]:
    if not ACTIONS_FILE.exists():
        save_actions([])
        return []
    try:
        with ACTIONS_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if isinstance(data, list):
            return [
                {
                    "title": str(item.get("title", "")).strip(),
                    "response": str(item.get("response", "")).strip(),
                }
                for item in data
                if isinstance(item, dict) and item.get("title") and item.get("response")
            ]
    except (json.JSONDecodeError, OSError):
        pass
    return []


def save_actions(actions: list[dict[str, str]]) -> None:
    with ACTIONS_FILE.open("w", encoding="utf-8") as file:
        json.dump(actions, file, ensure_ascii=False, indent=2)


def find_action(title: str) -> dict[str, str] | None:
    normalized = title.strip().lower()
    for action in get_actions():
        if action["title"].lower() == normalized:
            return action
    return None

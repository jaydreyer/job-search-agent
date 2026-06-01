"""On-disk feedback store: your decisions about postings + learned preferences.

`data/feedback.json` is the source of truth (you own it; survives offline). Two
effects on each run:
  • applied / dismissed roles are filtered out host-side before the agent scores
    them — a hard guarantee they never resurface.
  • freeform preferences are injected into the agent's scoring prompt.

Statuses: applied | dismissed | starred  (and "clear" to remove).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import ROOT

FEEDBACK_FILE = ROOT / "data" / "feedback.json"
HIDDEN = {"applied", "dismissed"}  # filtered out before the agent sees them


def key(company: str, title: str) -> str:
    """Stable identity for a posting (matches the dashboard's JS key)."""
    return f"{company.strip().lower()}||{title.strip().lower()}"


def load() -> dict:
    if FEEDBACK_FILE.exists():
        try:
            return json.loads(FEEDBACK_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {"items": {}, "preferences": []}


def save(data: dict) -> None:
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    FEEDBACK_FILE.write_text(json.dumps(data, indent=2))


def set_status(company: str, title: str, status: str, note: str = "") -> dict:
    data = load()
    k = key(company, title)
    if status == "clear":
        data["items"].pop(k, None)
    else:
        data["items"][k] = {
            "status": status,
            "company": company,
            "title": title,
            "note": note,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    save(data)
    return data


def add_preference(text: str) -> dict:
    data = load()
    text = text.strip()
    if text and text not in data["preferences"]:
        data["preferences"].append(text)
    save(data)
    return data


def remove_preference(text: str) -> dict:
    data = load()
    data["preferences"] = [p for p in data["preferences"] if p != text]
    save(data)
    return data


def excluded_keys() -> set[str]:
    """Keys for postings that should never be re-shown (applied/dismissed)."""
    return {k for k, v in load()["items"].items() if v.get("status") in HIDDEN}


def preferences() -> list[str]:
    return load().get("preferences", [])


def items() -> dict:
    return load().get("items", {})


def applied_titles() -> list[str]:
    return [f"{v['company']} — {v['title']}" for v in items().values() if v.get("status") == "applied"]

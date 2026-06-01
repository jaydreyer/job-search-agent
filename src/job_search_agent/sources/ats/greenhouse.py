"""Greenhouse public job board API.

Endpoint: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true
"""

from __future__ import annotations

import re
from datetime import datetime

import httpx

from ...config import AtsBoard
from ...models import JobPosting

_TAG = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _TAG.sub(" ", text or "").replace("&nbsp;", " ").strip()


def fetch_greenhouse(client: httpx.Client, board: AtsBoard) -> list[JobPosting]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{board.slug}/jobs"
    resp = client.get(url, params={"content": "true"})
    resp.raise_for_status()
    jobs = resp.json().get("jobs", [])
    company = board.label or board.slug
    out: list[JobPosting] = []
    for j in jobs:
        posted = None
        if j.get("updated_at"):
            try:
                posted = datetime.fromisoformat(j["updated_at"].replace("Z", "+00:00"))
            except ValueError:
                pass
        out.append(
            JobPosting(
                source=f"greenhouse:{board.slug}",
                title=j.get("title", "").strip(),
                company=company,
                location=(j.get("location") or {}).get("name"),
                url=j.get("absolute_url", ""),
                description=_strip_html(j.get("content", "")),
                posted_at=posted,
                raw=j,
            )
        )
    return out

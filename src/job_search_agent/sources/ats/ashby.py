"""Ashby public job board API.

Endpoint: https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true
"""

from __future__ import annotations

from datetime import datetime

import httpx

from ...config import AtsBoard
from ...models import JobPosting


def fetch_ashby(client: httpx.Client, board: AtsBoard) -> list[JobPosting]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{board.slug}"
    resp = client.get(url, params={"includeCompensation": "true"})
    resp.raise_for_status()
    data = resp.json()
    company = board.label or data.get("name") or board.slug
    out: list[JobPosting] = []
    for j in data.get("jobs", []):
        posted = None
        if j.get("publishedAt"):
            try:
                posted = datetime.fromisoformat(j["publishedAt"].replace("Z", "+00:00"))
            except ValueError:
                pass
        out.append(
            JobPosting(
                source=f"ashby:{board.slug}",
                title=j.get("title", "").strip(),
                company=company,
                location=j.get("location"),
                remote=j.get("isRemote"),
                url=j.get("jobUrl", ""),
                description=j.get("descriptionPlain", "") or j.get("description", ""),
                posted_at=posted,
                raw=j,
            )
        )
    return out

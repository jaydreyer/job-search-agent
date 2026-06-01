"""Lever public postings API.

Endpoint: https://api.lever.co/v0/postings/{slug}?mode=json
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from ...config import AtsBoard
from ...models import JobPosting


def fetch_lever(client: httpx.Client, board: AtsBoard) -> list[JobPosting]:
    url = f"https://api.lever.co/v0/postings/{board.slug}"
    resp = client.get(url, params={"mode": "json"})
    resp.raise_for_status()
    company = board.label or board.slug
    out: list[JobPosting] = []
    for j in resp.json():
        posted = None
        if j.get("createdAt"):
            try:
                posted = datetime.fromtimestamp(j["createdAt"] / 1000, tz=timezone.utc)
            except (ValueError, TypeError):
                pass
        cats = j.get("categories") or {}
        out.append(
            JobPosting(
                source=f"lever:{board.slug}",
                title=j.get("text", "").strip(),
                company=company,
                location=cats.get("location"),
                remote=("remote" in (cats.get("location") or "").lower()) or None,
                url=j.get("hostedUrl", ""),
                description=j.get("descriptionPlain", ""),
                posted_at=posted,
                raw=j,
            )
        )
    return out

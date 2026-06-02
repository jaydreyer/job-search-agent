"""Workable public widget API.

Board slug is the Workable account name (e.g. "huggingface"). Endpoint:
  GET https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true
"""

from __future__ import annotations

import re

import httpx

from ...config import AtsBoard
from ...models import JobPosting

_TAG = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _TAG.sub(" ", text or "").replace("&nbsp;", " ").strip()


def _location(job: dict) -> str | None:
    parts = [job.get("city"), job.get("state"), job.get("country")]
    loc = ", ".join(p for p in parts if p)
    return loc or ("Remote" if job.get("remote") else None)


def fetch_workable(client: httpx.Client, board: AtsBoard) -> list[JobPosting]:
    url = f"https://apply.workable.com/api/v1/widget/accounts/{board.slug}"
    resp = client.get(url, params={"details": "true"}, headers={"Accept": "application/json"})
    resp.raise_for_status()
    company = board.label or board.slug
    out: list[JobPosting] = []
    for job in resp.json().get("jobs", []):
        out.append(
            JobPosting(
                source=f"workable:{board.slug}",
                title=(job.get("title") or "").strip(),
                company=company,
                location=_location(job),
                remote=job.get("remote"),
                url=job.get("shortlink") or job.get("url") or job.get("application_url", ""),
                description=_strip_html(job.get("description", "")),
                raw=job,
            )
        )
    return out

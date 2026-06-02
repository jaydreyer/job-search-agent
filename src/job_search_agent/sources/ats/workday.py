"""Workday CXS public job-search API.

Board slug encodes the three Workday coordinates: "tenant/datacenter/site",
e.g. "automationanywhere/wd5/AutomationAnywhereJobs". Endpoint:
  POST https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs

The list endpoint returns title + location only (no description); that's enough
for the title-based shortlisting the agent does.
"""

from __future__ import annotations

import httpx

from ...config import AtsBoard
from ...models import JobPosting

_PAGE = 20
_MAX = 100


def fetch_workday(client: httpx.Client, board: AtsBoard) -> list[JobPosting]:
    try:
        tenant, dc, site = board.slug.split("/")
    except ValueError:
        raise ValueError(f"workday slug must be 'tenant/dc/site', got {board.slug!r}")
    host = f"{tenant}.{dc}.myworkdayjobs.com"
    url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    company = board.label or tenant

    out: list[JobPosting] = []
    offset = 0
    while offset < _MAX:
        resp = client.post(
            url,
            json={"appliedFacets": {}, "limit": _PAGE, "offset": offset, "searchText": ""},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        postings = data.get("jobPostings", [])
        if not postings:
            break
        for jp in postings:
            path = jp.get("externalPath", "")
            out.append(
                JobPosting(
                    source=f"workday:{tenant}",
                    title=(jp.get("title") or "").strip(),
                    company=company,
                    location=jp.get("locationsText"),
                    url=f"https://{host}/en-US/{site}{path}" if path else f"https://{host}/{site}",
                    description="",  # list endpoint has no body; title-based filtering suffices
                    raw=jp,
                )
            )
        offset += _PAGE
        if offset >= int(data.get("total", 0)):
            break
    return out

"""Adzuna aggregator source. Free API: https://developer.adzuna.com/"""

from __future__ import annotations

from datetime import datetime

import httpx

from ..config import SearchConfig, SearchQuery, Secrets
from ..models import JobPosting

BASE = "https://api.adzuna.com/v1/api/jobs"


class AdzunaSource:
    name = "adzuna"

    def __init__(self, secrets: Secrets, config: SearchConfig):
        self.app_id = secrets.adzuna_app_id
        self.app_key = secrets.adzuna_app_key
        self.config = config

    def _fetch_query(self, client: httpx.Client, query: SearchQuery) -> list[JobPosting]:
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": min(self.config.results_per_query, 50),
            "what": query.keywords,
            "content-type": "application/json",
        }
        if query.location:
            params["where"] = query.location
        url = f"{BASE}/{self.config.country}/search/1"
        resp = client.get(url, params=params, timeout=30)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        postings: list[JobPosting] = []
        for r in results:
            posted = None
            if r.get("created"):
                try:
                    posted = datetime.fromisoformat(r["created"].replace("Z", "+00:00"))
                except ValueError:
                    pass
            postings.append(
                JobPosting(
                    source="adzuna",
                    title=r.get("title", "").strip(),
                    company=(r.get("company") or {}).get("display_name", "Unknown"),
                    location=(r.get("location") or {}).get("display_name"),
                    url=r.get("redirect_url", ""),
                    description=r.get("description", ""),
                    salary_min=r.get("salary_min"),
                    salary_max=r.get("salary_max"),
                    salary_currency="USD" if self.config.country == "us" else None,
                    posted_at=posted,
                    raw=r,
                )
            )
        return postings

    def fetch(self) -> list[JobPosting]:
        if not (self.app_id and self.app_key):
            return []
        out: list[JobPosting] = []
        with httpx.Client() as client:
            for query in self.config.queries:
                try:
                    out.extend(self._fetch_query(client, query))
                except httpx.HTTPError as e:  # one bad query shouldn't kill the run
                    print(f"[adzuna] query {query.keywords!r} failed: {e}")
        return out

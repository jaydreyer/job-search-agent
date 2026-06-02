"""ATS board fetchers. These hit public JSON endpoints — no auth, no scraping."""

from __future__ import annotations

import httpx

from ...config import AtsBoard, SearchConfig
from ...models import JobPosting
from .ashby import fetch_ashby
from .greenhouse import fetch_greenhouse
from .lever import fetch_lever
from .workable import fetch_workable
from .workday import fetch_workday

_FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "workday": fetch_workday,
    "workable": fetch_workable,
}


class AtsSource:
    """Polls each configured company ATS board for its full job list."""

    name = "ats"

    def __init__(self, config: SearchConfig):
        self.boards: list[AtsBoard] = config.ats_boards

    def fetch(self) -> list[JobPosting]:
        out: list[JobPosting] = []
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            for board in self.boards:
                fetcher = _FETCHERS.get(board.provider)
                if not fetcher:
                    print(f"[ats] unknown provider {board.provider!r} for {board.slug}")
                    continue
                try:
                    out.extend(fetcher(client, board))
                except httpx.HTTPError as e:
                    print(f"[ats] {board.provider}:{board.slug} failed: {e}")
        return out

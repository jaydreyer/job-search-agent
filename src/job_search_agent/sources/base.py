"""Common interface for all job sources."""

from __future__ import annotations

from typing import Protocol

from ..models import JobPosting


class JobSource(Protocol):
    name: str

    def fetch(self) -> list[JobPosting]:
        """Return postings from this source. Should not raise on empty results."""
        ...

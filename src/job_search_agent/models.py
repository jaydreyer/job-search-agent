"""Canonical data models shared across all job sources."""

from __future__ import annotations

import hashlib
from datetime import datetime

from pydantic import BaseModel, Field


class JobPosting(BaseModel):
    """A single job posting, normalized into a common shape across all sources."""

    source: str  # e.g. "adzuna", "greenhouse:stripe", "indeed-mcp"
    title: str
    company: str
    location: str | None = None
    remote: bool | None = None
    url: str
    description: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    posted_at: datetime | None = None
    raw: dict = Field(default_factory=dict, repr=False)

    @property
    def fingerprint(self) -> str:
        """Stable id for dedupe across runs/sources (company+title+location)."""
        key = f"{self.company.strip().lower()}|{self.title.strip().lower()}|{(self.location or '').strip().lower()}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]


class ScoredJob(BaseModel):
    """A posting with the resume-match assessment attached."""

    job: JobPosting
    score: int = Field(ge=0, le=100)
    verdict: str  # one-line summary, e.g. "Strong match — direct title + stack overlap"
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    scored_at: datetime = Field(default_factory=datetime.utcnow)

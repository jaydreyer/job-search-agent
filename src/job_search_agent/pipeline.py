"""Orchestration: fetch -> dedupe -> score -> filter-new -> digest."""

from __future__ import annotations

from .config import SearchConfig, Secrets, load_resume
from .digest import write_digest
from .models import JobPosting, ScoredJob
from .scoring import ResumeScorer
from .sources.adzuna import AdzunaSource
from .sources.ats import AtsSource
from .store import SeenStore


def dedupe(postings: list[JobPosting]) -> list[JobPosting]:
    seen: dict[str, JobPosting] = {}
    for p in postings:
        if not p.title or not p.url:
            continue
        seen.setdefault(p.fingerprint, p)
    return list(seen.values())


def run(only_new: bool = True, extra_postings: list[JobPosting] | None = None) -> list[ScoredJob]:
    secrets = Secrets()
    config = SearchConfig.load()
    resume = load_resume()

    # 1. Fetch from all configured sources.
    postings: list[JobPosting] = []
    postings += AdzunaSource(secrets, config).fetch()
    postings += AtsSource(config).fetch()
    if extra_postings:  # e.g. results piped in from MCP connectors
        postings += extra_postings
    print(f"[pipeline] fetched {len(postings)} raw postings")

    # 2. Dedupe.
    postings = dedupe(postings)
    print(f"[pipeline] {len(postings)} after dedupe")

    # 3. Score against resume.
    scorer = ResumeScorer(secrets.anthropic_api_key, resume, model=config.scoring_model)
    scored = scorer.score_all(postings)

    # 4. Optionally keep only postings we haven't recorded before.
    store = SeenStore()
    try:
        fresh = store.filter_new(scored) if only_new else scored
        store.record(scored)
    finally:
        store.close()
    print(f"[pipeline] {len(fresh)} new scored postings")

    # 5. Write digest.
    md, csv = write_digest(fresh, config.min_score_for_digest)
    print(f"[pipeline] digest -> {md}\n[pipeline] csv    -> {csv}")
    return fresh

"""Render scored jobs into a markdown digest and a CSV."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from .config import ROOT
from .models import ScoredJob

OUT_DIR = ROOT / "data" / "digests"


def _salary(job) -> str:
    if job.salary_min or job.salary_max:
        lo = f"{job.salary_min:,.0f}" if job.salary_min else "?"
        hi = f"{job.salary_max:,.0f}" if job.salary_max else "?"
        cur = job.salary_currency or ""
        return f"{cur}{lo}–{hi}"
    return "—"


def render_markdown(scored: list[ScoredJob], min_score: int) -> str:
    ranked = sorted(scored, key=lambda s: s.score, reverse=True)
    top = [s for s in ranked if s.score >= min_score]
    lines = [
        f"# Job match digest — {date.today().isoformat()}",
        "",
        f"{len(top)} new matches at or above score {min_score} "
        f"(out of {len(scored)} scored).",
        "",
    ]
    for s in top:
        j = s.job
        lines += [
            f"## {s.score} · [{j.title}]({j.url}) — {j.company}",
            f"*{j.location or 'location n/a'} · {_salary(j)} · `{j.source}`*",
            "",
            f"**{s.verdict}**",
            "",
        ]
        if s.strengths:
            lines.append("**Strengths:** " + "; ".join(s.strengths))
        if s.gaps:
            lines.append("**Gaps:** " + "; ".join(s.gaps))
        lines.append("")
    return "\n".join(lines)


def write_digest(scored: list[ScoredJob], min_score: int) -> tuple[Path, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()
    md_path = OUT_DIR / f"{stamp}.md"
    csv_path = OUT_DIR / f"{stamp}.csv"

    md_path.write_text(render_markdown(scored, min_score))

    with csv_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["score", "title", "company", "location", "salary", "source", "url", "verdict"])
        for s in sorted(scored, key=lambda s: s.score, reverse=True):
            j = s.job
            w.writerow(
                [s.score, j.title, j.company, j.location or "", _salary(j), j.source, j.url, s.verdict]
            )
    return md_path, csv_path

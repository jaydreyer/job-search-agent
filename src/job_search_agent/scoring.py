"""Resume-match scoring via the Claude API.

The resume is sent as a cached system block so it's only billed once per ~5 min
window even across hundreds of postings. Each posting is scored independently and
asked for a strict JSON verdict.
"""

from __future__ import annotations

import json

from anthropic import Anthropic

from .models import JobPosting, ScoredJob

_SYSTEM_INSTRUCTIONS = """You are a precise technical recruiter. Score how well a single \
job posting matches the candidate's resume on a 0-100 scale.

Scoring guidance:
- 90-100: Direct title + strong stack/domain overlap; candidate clearly qualified.
- 70-89: Good match; most requirements met, minor gaps.
- 50-69: Plausible stretch; meaningful gaps or seniority mismatch.
- 0-49: Weak match; wrong domain, seniority, or core skills missing.

Be skeptical and specific. Penalize seniority mismatches and missing must-have skills.
Respond with ONLY a JSON object, no prose, in this exact shape:
{"score": <int 0-100>, "verdict": "<one sentence>", "strengths": ["..."], "gaps": ["..."]}"""


class ResumeScorer:
    def __init__(self, api_key: str, resume: str, model: str = "claude-opus-4-8"):
        self.client = Anthropic(api_key=api_key)
        self.resume = resume
        self.model = model

    def _system_blocks(self) -> list[dict]:
        return [
            {"type": "text", "text": _SYSTEM_INSTRUCTIONS},
            {
                "type": "text",
                "text": f"CANDIDATE RESUME:\n\n{self.resume}",
                "cache_control": {"type": "ephemeral"},  # cached across calls
            },
        ]

    def score(self, job: JobPosting) -> ScoredJob:
        desc = job.description[:6000]
        user = (
            f"JOB POSTING\nTitle: {job.title}\nCompany: {job.company}\n"
            f"Location: {job.location or 'n/a'}\n\nDescription:\n{desc}"
        )
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=600,
            system=self._system_blocks(),
            messages=[{"role": "user", "content": user}],
        )
        text = resp.content[0].text.strip()
        data = _parse_json(text)
        return ScoredJob(
            job=job,
            score=int(max(0, min(100, data.get("score", 0)))),
            verdict=data.get("verdict", ""),
            strengths=data.get("strengths", []),
            gaps=data.get("gaps", []),
        )

    def score_all(self, jobs: list[JobPosting]) -> list[ScoredJob]:
        out: list[ScoredJob] = []
        for i, job in enumerate(jobs, 1):
            try:
                out.append(self.score(job))
            except Exception as e:  # noqa: BLE001 - keep going on individual failures
                print(f"[score] {i}/{len(jobs)} failed for {job.title!r}: {e}")
        return out


def _parse_json(text: str) -> dict:
    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start : end + 1])
        raise

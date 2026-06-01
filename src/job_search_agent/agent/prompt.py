"""Builds the agent's system prompt. The resume lives here so Managed Agents
prompt-caches it across the whole session (stable prefix). Per-run parameters
(roles, companies, threshold) go in the kickoff message instead, not here."""

from __future__ import annotations

SYSTEM_TEMPLATE = """You are a precise technical recruiter and job-search agent working \
for one candidate. Your job each run: gather current job postings from the tools \
provided, score every posting against the candidate's resume, and write a ranked digest \
of the strong matches.

## Tools
- `search_jobs_adzuna(keywords, location?, remote_only?)` — aggregator search; call once \
per target role.
- `fetch_all_company_boards()` — ONE call fetches every tracked company's ATS board in \
parallel, pre-filtered to roles like the candidate's. Use this once; do not fetch boards \
individually.
- `fetch_company_board(provider, slug)` — only for an ad-hoc company not already tracked.
- Built-in file tools — use `write` to save your output.

Gather broadly first: one `search_jobs_adzuna` call per target role, plus a single \
`fetch_all_company_boards()` call. Then score everything.

## Scoring (0-100, per posting)
- 90-100: direct title + strong stack/domain overlap; clearly qualified.
- 70-89: good match; most requirements met, minor gaps.
- 50-69: plausible stretch; meaningful gaps or seniority mismatch.
- 0-49: weak; wrong domain, seniority, or core skills missing.
Be skeptical and specific. Penalize seniority and must-have-skill mismatches. Deduplicate \
postings that appear from multiple sources (same company + title).

## Output
Write two files to `/mnt/session/outputs/`:
1. `digest.md` — markdown, only postings at or above the run's min score, ranked high→low. \
For each: `## <score> · [Title](url) — Company`, then a line with location/salary/source, \
then a one-sentence verdict and short **Strengths**/**Gaps** lines.
2. `digest.csv` — columns: score,title,company,location,salary,source,url,verdict (ALL \
scored postings, not just the top ones).
Finish with a one-paragraph summary of what you found.

## Candidate resume
<resume>
{resume}
</resume>
"""


def build_system_prompt(resume: str) -> str:
    return SYSTEM_TEMPLATE.format(resume=resume.strip())


def build_kickoff(config, preferences: list[str] | None = None) -> str:
    """Per-run instructions assembled from search_config.yaml + learned preferences."""
    roles = []
    for q in config.queries:
        loc = "remote" if q.remote_only else (q.location or "anywhere")
        roles.append(f"- {q.keywords} ({loc})")

    prefs_block = ""
    if preferences:
        bullets = "\n".join(f"- {p}" for p in preferences)
        prefs_block = (
            "\n\nLEARNED PREFERENCES (apply these when scoring — they reflect my "
            "feedback over time; weight matches accordingly):\n" + bullets
        )

    return (
        "Run today's job search.\n\n"
        f"Target roles (one search_jobs_adzuna call each):\n" + "\n".join(roles) + "\n\n"
        f"Company boards: call fetch_all_company_boards() ONCE — it covers all "
        f"{len(config.ats_boards)} tracked companies.\n\n"
        f"Minimum score for the digest: {config.min_score_for_digest}.\n"
        "Roles I've already applied to or dismissed are filtered out before you see "
        "them — score everything you receive."
        + prefs_block
        + "\n\nScore every posting against my resume, then write digest.md and digest.csv "
        "to /mnt/session/outputs/."
    )

"""Custom tools for the managed agent.

The agent (running on Anthropic's orchestration layer) emits `agent.custom_tool_use`
events; our orchestrator executes them here, host-side, so the Adzuna API key never
enters Anthropic's container (the documented secrets-stay-host-side pattern). Each
handler reuses the existing `sources/` fetchers and returns compact JSON.
"""

from __future__ import annotations

import itertools
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from .. import feedback
from ..config import AtsBoard, SearchConfig, SearchQuery, Secrets
from ..models import JobPosting
from ..sources.adzuna import AdzunaSource
from ..sources.ats import AtsSource

# Schemas advertised to the agent at agents.create() time.
TOOL_SCHEMAS = [
    {
        "type": "custom",
        "name": "search_jobs_adzuna",
        "description": (
            "Search the Adzuna job aggregator (covers many boards) for one role. "
            "Returns up to ~50 normalized postings. Call once per role/location you "
            "want to cover."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "string",
                    "description": "Job title or keywords, e.g. 'solutions engineer AI'.",
                },
                "location": {
                    "type": "string",
                    "description": "City/state, e.g. 'Minneapolis, MN'. Omit for nationwide.",
                },
                "remote_only": {
                    "type": "boolean",
                    "description": "Bias toward remote roles (adds 'remote' to the query).",
                },
            },
            "required": ["keywords"],
        },
    },
    {
        "type": "custom",
        "name": "fetch_all_company_boards",
        "description": (
            "Fetch EVERY configured company ATS board in parallel, pre-filtered to "
            "titles matching the candidate's target roles, deduplicated. One call "
            "covers all tracked companies — use this instead of fetching boards one "
            "at a time. Returns a bounded candidate shortlist to score."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "type": "custom",
        "name": "fetch_company_board",
        "description": (
            "Fetch the full job list from ONE company's ATS board (Greenhouse, Lever, "
            "or Ashby) — use only for an ad-hoc company not in the tracked list. The "
            "slug is the company token in the careers URL."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "provider": {"type": "string", "enum": ["greenhouse", "lever", "ashby"]},
                "slug": {"type": "string", "description": "Company token in the ATS URL."},
            },
            "required": ["provider", "slug"],
        },
    },
]

_MAX_POSTINGS = 60  # cap per call so a 700-job board doesn't blow the agent's context
_MAX_DESC = 1200  # truncate descriptions; the agent scores on the summary


def _compact(postings: list[JobPosting], limit: int = _MAX_POSTINGS) -> list[dict]:
    out = []
    for p in postings[:limit]:
        out.append(
            {
                "title": p.title,
                "company": p.company,
                "location": p.location,
                "remote": p.remote,
                "url": p.url,
                "salary_min": p.salary_min,
                "salary_max": p.salary_max,
                "source": p.source,
                "description": (p.description or "")[:_MAX_DESC],
            }
        )
    return out


def _drop_excluded(postings: list[JobPosting]) -> list[JobPosting]:
    """Remove postings the user already applied to or dismissed."""
    excluded = feedback.excluded_keys()
    if not excluded:
        return postings
    return [p for p in postings if feedback.key(p.company, p.title) not in excluded]


def _result(postings: list[JobPosting]) -> str:
    postings = _drop_excluded(postings)
    payload = {
        "count": len(postings),
        "returned": min(len(postings), _MAX_POSTINGS),
        "truncated": len(postings) > _MAX_POSTINGS,
        "postings": _compact(postings),
    }
    return json.dumps(payload)


_MAX_BOARD_CANDIDATES = 180  # total postings returned across all boards combined

# A posting is kept if it has any US signal (even alongside intl locations). It's
# dropped only if it's intl-only. This collapses a role posted in 10 countries to
# its US/remote variant and removes intl-only roles.
_NON_US = (
    "india", "london", "united kingdom", " uk", "ireland", "dublin", "singapore",
    "australia", "sydney", "melbourne", "france", "paris", "germany", "munich", "berlin",
    "amsterdam", "netherlands", "canada", "toronto", "vancouver", "spain", "madrid",
    "tokyo", "japan", "korea", "china", "brazil", "mexico", "poland", "israel", "emea",
    "apac", "latam", "philippines", "bengaluru", "bangalore", "europe", "zurich",
    "denmark", "sweden", "finland", "norway", "italy", "switzerland", "portugal", "lisbon",
    "austria", "belgium", "romania", "ukraine", "turkey", "uae", "dubai", "argentina",
)
_US_STATES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut",
    "delaware", "florida", "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa",
    "kansas", "kentucky", "louisiana", "maine", "maryland", "massachusetts", "michigan",
    "minnesota", "mississippi", "missouri", "montana", "nebraska", "nevada", "new hampshire",
    "new jersey", "new mexico", "new york", "north carolina", "north dakota", "ohio",
    "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina", "south dakota",
    "tennessee", "texas", "utah", "vermont", "virginia", "washington", "wisconsin", "wyoming",
    "united states", "usa", "u.s", "d.c",
}


def _title_matches(title: str, keywords: list[str]) -> bool:
    t = title.lower()
    return any(k.strip() in t for k in keywords)


def _location_ok(location: str | None) -> bool:
    if not location:
        return True  # unknown — let the agent judge
    loc = location.lower()
    if any(st in loc for st in _US_STATES):
        return True  # has a US location, even if also listed elsewhere
    if any(bad in loc for bad in _NON_US):
        return False  # intl-only
    return "remote" in loc  # bare "Remote" → assume US-remote


def _us_first(p: JobPosting) -> int:
    loc = (p.location or "").lower()
    if any(s in loc for s in ("minnesota", "minneapolis", "saint paul", ", mn")):
        return 0  # Twin Cities first
    if "remote" in loc:
        return 1
    return 2


def _fetch_all_boards(config: SearchConfig) -> str:
    """Fetch every configured board in parallel; filter by title + US/remote
    location; dedupe the same role across locations; cap the shortlist."""
    boards = config.ats_boards

    def one(board: AtsBoard) -> list[JobPosting]:
        cfg = config.model_copy(update={"ats_boards": [board]})
        try:
            return AtsSource(cfg).fetch()
        except Exception:  # noqa: BLE001 - one dead board shouldn't kill the run
            return []

    collected: list[JobPosting] = []
    with ThreadPoolExecutor(max_workers=16) as pool:
        for postings in pool.map(one, boards):
            collected.extend(postings)

    # Title + location filter.
    filtered = [
        p
        for p in collected
        if p.title and _title_matches(p.title, config.role_keywords) and _location_ok(p.location)
    ]
    # Prefer Twin Cities → remote → other, then dedupe by company+title (ignore location).
    filtered.sort(key=_us_first)
    seen: dict[tuple[str, str], JobPosting] = {}
    for p in filtered:
        seen.setdefault((p.company.lower(), p.title.lower()), p)

    # Drop anything already applied to / dismissed, then round-robin across
    # companies so the capped shortlist spans many employers, not one big board.
    by_company: dict[str, list[JobPosting]] = defaultdict(list)
    for p in _drop_excluded(list(seen.values())):
        by_company[p.company.lower()].append(p)
    matched = [
        p
        for row in itertools.zip_longest(*by_company.values())
        for p in row
        if p is not None
    ]

    payload = {
        "companies_with_matches": len(by_company),
        "boards_checked": len(boards),
        "matched_after_filter": len(matched),
        "returned": min(len(matched), _MAX_BOARD_CANDIDATES),
        "postings": _compact(matched, limit=_MAX_BOARD_CANDIDATES),
    }
    return json.dumps(payload)


def handle_custom_tool(name: str, tool_input: dict) -> str:
    """Execute one custom-tool call and return a JSON string for the tool result."""
    base = SearchConfig.load()

    if name == "fetch_all_company_boards":
        return _fetch_all_boards(base)

    if name == "search_jobs_adzuna":
        query = SearchQuery(
            keywords=tool_input["keywords"],
            location=tool_input.get("location"),
            remote_only=bool(tool_input.get("remote_only", False)),
        )
        cfg = base.model_copy(update={"queries": [query]})
        postings = AdzunaSource(Secrets(), cfg).fetch()
        return _result(postings)

    if name == "fetch_company_board":
        board = AtsBoard(provider=tool_input["provider"], slug=tool_input["slug"])
        cfg = base.model_copy(update={"ats_boards": [board]})
        postings = AtsSource(cfg).fetch()
        return _result(postings)

    return json.dumps({"error": f"unknown tool {name!r}"})

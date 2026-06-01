"""Cheap data-path check: run the custom tools against live Adzuna + ATS boards
WITHOUT creating an agent or session. Validates your Adzuna key and shows the
JSON the agent will receive. Costs nothing but the (free) Adzuna calls.

    uv run jobsearch-agent-dryrun
"""

from __future__ import annotations

import json

from ..config import SearchConfig
from .tools import handle_custom_tool


def main() -> None:
    config = SearchConfig.load()
    print("== Adzuna searches ==")
    for q in config.queries:
        out = json.loads(
            handle_custom_tool(
                "search_jobs_adzuna",
                {"keywords": q.keywords, "location": q.location, "remote_only": q.remote_only},
            )
        )
        loc = "remote" if q.remote_only else (q.location or "anywhere")
        note = " (no Adzuna key?)" if out["count"] == 0 else ""
        print(f"  {q.keywords!r} [{loc}]: {out['count']} postings{note}")

    print("\n== Company boards ==")
    for b in config.ats_boards:
        out = json.loads(
            handle_custom_tool("fetch_company_board", {"provider": b.provider, "slug": b.slug})
        )
        sample = out["postings"][0]["title"] if out["postings"] else "—"
        print(f"  {b.provider}:{b.slug}: {out['count']} postings (e.g. {sample})")

    print("\nData path OK — the agent will receive this shape of JSON per tool call.")


if __name__ == "__main__":
    main()

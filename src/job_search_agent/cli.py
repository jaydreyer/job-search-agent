"""Command-line entrypoint: `jobsearch run`."""

from __future__ import annotations

import argparse

from rich.console import Console
from rich.table import Table

from .pipeline import run

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and score jobs against your resume.")
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run the full fetch+score pipeline.")
    run_p.add_argument(
        "--all", action="store_true", help="Include already-seen postings (default: new only)."
    )

    args = parser.parse_args()
    if args.command != "run":
        parser.print_help()
        return

    scored = run(only_new=not args.all)
    ranked = sorted(scored, key=lambda s: s.score, reverse=True)

    table = Table(title="New matches")
    table.add_column("Score", justify="right", style="bold")
    table.add_column("Title")
    table.add_column("Company")
    table.add_column("Source", style="dim")
    for s in ranked[:25]:
        table.add_row(str(s.score), s.job.title, s.job.company, s.job.source)
    console.print(table)


if __name__ == "__main__":
    main()

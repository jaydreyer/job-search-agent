"""Terminal access to the feedback store (the dashboard buttons are the main UI).

    uv run jobsearch-feedback applied "OpenAI" "Solutions Engineer, Pre-Sales"
    uv run jobsearch-feedback dismiss "Stripe" "Backend Engineer"
    uv run jobsearch-feedback star    "Anthropic" "Applied AI Architect, Commercial"
    uv run jobsearch-feedback pref "Prefer hands-on AI eng over pure sales"
    uv run jobsearch-feedback list
"""

from __future__ import annotations

import argparse

from . import feedback


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage job-search feedback.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for status in ("applied", "dismiss", "star", "clear"):
        p = sub.add_parser(status)
        p.add_argument("company")
        p.add_argument("title")
    pref = sub.add_parser("pref")
    pref.add_argument("text")
    sub.add_parser("list")

    args = parser.parse_args()
    status_map = {"applied": "applied", "dismiss": "dismissed", "star": "starred", "clear": "clear"}

    if args.cmd in status_map:
        feedback.set_status(args.company, args.title, status_map[args.cmd])
        print(f"{args.cmd}: {args.company} — {args.title}")
    elif args.cmd == "pref":
        feedback.add_preference(args.text)
        print(f"added preference: {args.text}")
    elif args.cmd == "list":
        items = feedback.items()
        if items:
            print("Feedback:")
            for v in items.values():
                print(f"  [{v['status']:9}] {v['company']} — {v['title']}")
        prefs = feedback.preferences()
        if prefs:
            print("Preferences:")
            for p in prefs:
                print(f"  - {p}")
        if not items and not prefs:
            print("No feedback yet.")


if __name__ == "__main__":
    main()

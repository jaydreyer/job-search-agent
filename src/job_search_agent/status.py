"""Did the daily run happen? One command to check.

    uv run jobsearch-status
"""

from __future__ import annotations

import re
import subprocess
from datetime import date, datetime
from pathlib import Path

from .config import ROOT

DIGEST_DIR = ROOT / "data" / "digests"
RUN_LOG = DIGEST_DIR / "run.log"
DASHBOARD = DIGEST_DIR / "index.html"
LABEL = "com.jaydreyer.jobsearch"
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _launchd_exit() -> int | None:
    try:
        out = subprocess.run(
            ["launchctl", "list", LABEL], capture_output=True, text=True, timeout=5
        )
    except Exception:  # noqa: BLE001
        return None
    if out.returncode != 0:
        return None
    m = re.search(r'"LastExitStatus"\s*=\s*(\d+)', out.stdout)
    return int(m.group(1)) if m else None


def _newest_digest() -> tuple[Path, str, int] | None:
    csvs = sorted(DIGEST_DIR.glob("*-digest.csv"))
    if not csvs:
        return None
    path = csvs[-1]
    m = _DATE_RE.search(path.name)
    run_date = m.group(1) if m else "?"
    rows = max(0, len(path.read_text().splitlines()) - 1)  # minus header
    return path, run_date, rows


def main() -> None:
    today = date.today().isoformat()
    print(f"Today: {today}\n")

    # Is the schedule installed?
    exit_code = _launchd_exit()
    if exit_code is None:
        print("⏰ Schedule: NOT loaded (run: launchctl load ~/Library/LaunchAgents/com.jaydreyer.jobsearch.plist)")
    else:
        verdict = "ok" if exit_code == 0 else f"FAILED (exit {exit_code} — see run.log)"
        print(f"⏰ Schedule: loaded · last exit {verdict}")

    # Did today's digest get produced?
    newest = _newest_digest()
    if newest:
        path, run_date, rows = newest
        ran_today = run_date == today
        mark = "✅" if ran_today else "⚠️ "
        print(f"{mark} Latest digest: {run_date} ({rows} scored postings) — {path.name}")
        if not ran_today:
            print(f"   (no digest dated {today} yet — run may not have fired)")
    else:
        print("⚠️  No digests found yet.")

    # Dashboard freshness
    if DASHBOARD.exists():
        ts = datetime.fromtimestamp(DASHBOARD.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"📊 Dashboard last built: {ts}  (open: file://{DASHBOARD})")

    # Tail the log
    if RUN_LOG.exists():
        tail = RUN_LOG.read_text().splitlines()[-6:]
        print("\n— last log lines —")
        for line in tail:
            print(f"  {line}")


if __name__ == "__main__":
    main()

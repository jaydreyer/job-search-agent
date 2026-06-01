#!/bin/bash
# Wrapper for the daily scheduled run. launchd/cron calls this.
# launchd runs with a minimal PATH, so add Homebrew where uv lives.
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd "$(dirname "$0")/.."
mkdir -p data/digests
echo "=== run $(date) ===" >> data/digests/run.log
exec uv run jobsearch-agent-run >> data/digests/run.log 2>&1

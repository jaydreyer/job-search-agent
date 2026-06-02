#!/bin/bash
# Always-on dashboard server (launchd keeps it alive). Serves localhost:8137.
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export JOBSEARCH_NO_OPEN=1   # don't pop a browser tab on every (re)start
cd "$(dirname "$0")/.."
exec uv run jobsearch-serve

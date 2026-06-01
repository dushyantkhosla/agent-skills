#!/usr/bin/env bash
# Web search: tries ddgr (uvx) first, falls back to Brave API (Python)
# Usage: search.sh "query" [num_results]
#
# Dependencies: BRAVE_API_KEY env var (for fallback). ddgr needs nothing.

set -euo pipefail

QUERY="${1:?Usage: search.sh \"query\" [num_results]}"
NUM="${2:-10}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Try ddgr via uvx first (no API key needed)
if uvx ddgr -x --np -n "$NUM" "$QUERY" 2>&1; then
    exit 0
fi

echo "ddgr failed or rate-limited, falling back to Brave Search API..."

# Fallback: Python script using BRAVE_API_KEY
uv run "$SCRIPT_DIR/search.py" "$QUERY" -n "$NUM"

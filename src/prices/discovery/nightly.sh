#!/usr/bin/env bash
# Nightly discovery on a8: spend the ddgs budgets, then triage what they found.
# cron: 0 1 * * *  setsid nohup bash <this file> </dev/null >/dev/null 2>&1
# One lock for every discovery job, so the Monday session never overlaps a search.
set -u
cd "$(dirname "$(readlink -f "$0")")/../.."
LOGS=~/po/logs/discovery
mkdir -p "$LOGS"
LOG="$LOGS/nightly_$(date +%F).log"
exec 9>"$LOGS/.lock"
if ! flock -n 9; then
  echo "$(date -Is) skipped: another discovery job holds the lock" >>"$LOG"
  exit 0
fi
po() { ~/venv/bin/python -c "import sys;sys.argv=['po','prices','discovery']+sys.argv[1:];from cli import main;main()" "$@"; }
{
  echo "== $(date -Is) search"; po search
  echo "== $(date -Is) triage"; po triage
  echo "== $(date -Is) status"; po status
  echo "== $(date -Is) done"
} >>"$LOG" 2>&1

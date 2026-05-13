#!/bin/bash
# Kill the python PID for `po text collect --country X [--source Y]` only.
# Leaves the bash wrapper shell alive so xargs sees a clean child exit (signal
# 143) and emits [FAIL ] cleanly without aborting the entire queue.
#
# Usage:
#   kill_collect_python.sh <country>                # whole-country job
#   kill_collect_python.sh <country> <source>       # per-source job
#
# The lesson behind this script (2026-05-04 honduras incident): if you `kill`
# the wrapper shell process (the one running /tmp/refresh_*_runner.sh), xargs
# sees its child die with signal 15 and aborts the entire queue. Then ~20
# countries silently never start until you build a resume queue. Killing the
# python only avoids this entirely.

set -euo pipefail

COUNTRY="${1:-}"
SOURCE="${2:-}"

if [ -z "$COUNTRY" ]; then
  echo "usage: $0 <country> [<source>]" >&2
  exit 2
fi

if [ -n "$SOURCE" ]; then
  PATTERN="po text collect --country $COUNTRY --source $SOURCE"
else
  PATTERN="po text collect --country $COUNTRY"
fi

# Match exactly the python command (not the bash wrapper).
PIDS=$(pgrep -f -x "$(which poetry || echo poetry) run $PATTERN" 2>/dev/null || true)
if [ -z "$PIDS" ]; then
  # Fallback: looser match against the venv python
  PIDS=$(ps aux | grep -F "$PATTERN" | grep -v grep | grep "/.venv/bin/" | awk '{print $2}' || true)
fi

if [ -z "$PIDS" ]; then
  echo "no python PID found matching: $PATTERN"
  exit 1
fi

for PID in $PIDS; do
  echo "killing python PID $PID ($PATTERN)"
  kill "$PID" 2>&1 || true
done

# Brief wait + verify
sleep 2
REMAIN=$(ps -p $PIDS 2>/dev/null | tail -n +2 || true)
if [ -n "$REMAIN" ]; then
  echo "WARN: still alive after SIGTERM:" >&2
  echo "$REMAIN" >&2
  exit 1
fi

echo "killed cleanly. wrapper shell will emit [FAIL ] on its own."

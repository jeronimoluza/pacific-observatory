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
  PATTERN="text collect --country $COUNTRY --source $SOURCE"
else
  PATTERN="text collect --country $COUNTRY"
fi

# Match on the subcommand and its arguments, not on the entrypoint. The console
# script (`po`), the module runner (`run.py`) and a bare venv python all reach
# the same code, and which one shows up in the process table depends on how the
# caller resolved `po` -- a shim or a poetry venv. Anchoring on `po ` or on
# `/.venv/bin/` matched neither, so every kill was a no-op and the wall-clock
# cap logged TIMEOUT while the collect ran on (2026-09-08 ssa refresh: four
# sources still running at 17m against a 3m budget).
#
# The wrapper stays safe because runner.sh's own command line is
# `runner.sh <country>|<source>` -- it never contains "text collect".
PIDS=$(pgrep -f "$PATTERN" 2>/dev/null || true)

# A country-only job must not reap that country's per-source collects, which
# carry the same prefix.
if [ -z "$SOURCE" ] && [ -n "$PIDS" ]; then
  KEPT=""
  for PID in $PIDS; do
    case "$(ps -o command= -p "$PID" 2>/dev/null)" in
      *--source*) ;;
      *) KEPT="$KEPT $PID" ;;
    esac
  done
  PIDS=$(echo "$KEPT" | tr -s ' ' '\n' | sed '/^$/d')
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

#!/bin/bash
# Per-source runner for refresh-text-region.
# Emits timestamped [START]/[DONE]/[FAIL]/[STUCK]/[TIMEOUT] events (epoch
# seconds at end) so render_collect_report.py can compute durations.
#
# Args: <country>|<source>   (source may be empty → run whole country)
#
# Env knobs:
#   MAX_SOURCE_SECONDS — hard wall-clock cap per source (default 300 = 5min);
#                        on hit, python is killed and [TIMEOUT] is emitted
#   STALL_SECONDS    — seconds of post-warning zero-growth before killing (default 300)
#   POLL_SECONDS     — sampling cadence (default 30)
#   DATA_BASE        — root for news.csv resolution (default $(pwd)/data/text)
#   KILL_SCRIPT      — kill_collect_python.sh helper path
#   DISABLE_WATCHDOG=1 — bypass the watchdog (legacy plain-wrap behaviour)
set -u

JOB="$1"
COUNTRY="${JOB%|*}"
SOURCE="${JOB#*|}"

if [ -n "$SOURCE" ]; then
  TAG="${COUNTRY}__${SOURCE}"
  ARGS=(--country "$COUNTRY" --source "$SOURCE")
else
  TAG="$COUNTRY"
  ARGS=(--country "$COUNTRY")
fi

if [ -n "${MAX_ARTICLES:-}" ]; then
  ARGS+=(--max-articles "$MAX_ARTICLES")
fi

LOG="/tmp/refresh_${TAG}.log"
echo "[START] $TAG @ $(date +%s)"

if [ "${DISABLE_WATCHDOG:-0}" = "1" ]; then
  poetry run po text collect "${ARGS[@]}" > "$LOG" 2>&1
  STATUS=$?
  if [ $STATUS -eq 0 ]; then
    echo "[DONE ] $TAG @ $(date +%s)"
  else
    echo "[FAIL ] $TAG (exit $STATUS) @ $(date +%s)"
    tail -3 "$LOG"
  fi
  exit $STATUS
fi

MAX_SOURCE_SECONDS="${MAX_SOURCE_SECONDS:-300}"
STALL_SECONDS="${STALL_SECONDS:-300}"
POLL_SECONDS="${POLL_SECONDS:-30}"
DATA_BASE="${DATA_BASE:-$(pwd)/data/text}"
KILL_SCRIPT="${KILL_SCRIPT:-$(pwd)/.claude/skills/refresh-text-region/scripts/kill_collect_python.sh}"
WARNING_RE="after [0-9]+ article attempts, 0 were successfully scraped"

kill_python() {
  if [ -x "$KILL_SCRIPT" ]; then
    "$KILL_SCRIPT" "$COUNTRY" "$SOURCE" >&2 || true
  else
    if [ -n "$SOURCE" ]; then
      PIDS=$(ps aux | grep -F "po text collect --country $COUNTRY --source $SOURCE" | grep -v grep | grep "/.venv/bin/" | awk '{print $2}')
    else
      PIDS=$(ps aux | grep -F "po text collect --country $COUNTRY" | grep -v -- "--source" | grep -v grep | grep "/.venv/bin/" | awk '{print $2}')
    fi
    for PID in $PIDS; do kill -TERM "$PID" 2>/dev/null || true; done
  fi
}

if [ -n "$SOURCE" ]; then
  FIND_PATTERN="*/${COUNTRY}/${SOURCE}/news.csv"
else
  FIND_PATTERN="*/${COUNTRY}/*/news.csv"
fi

csv_size() {
  local total=0 f sz
  while IFS= read -r f; do
    [ -f "$f" ] || continue
    sz=$(stat -f%z "$f" 2>/dev/null || stat -c%s "$f" 2>/dev/null || echo 0)
    total=$(( total + sz ))
  done < <(find "$DATA_BASE" -path "$FIND_PATTERN" 2>/dev/null)
  echo "$total"
}

start_at=$(date +%s)
poetry run po text collect "${ARGS[@]}" > "$LOG" 2>&1 &
WRAP_PID=$!

last_size=$(csv_size)
last_growth_at=$start_at
warning_seen_at=""
stuck_triggered=0
timeout_triggered=0

while kill -0 "$WRAP_PID" 2>/dev/null; do
  sleep "$POLL_SECONDS"
  now=$(date +%s)
  if [ "$(( now - start_at ))" -ge "$MAX_SOURCE_SECONDS" ]; then
    echo "[TIMEOUT] $TAG (exceeded ${MAX_SOURCE_SECONDS}s wall; killing python) @ $now"
    kill_python
    timeout_triggered=1
    break
  fi
  cur_size=$(csv_size)
  if [ "$cur_size" != "$last_size" ]; then
    last_size="$cur_size"
    last_growth_at=$now
  fi
  if [ -z "$warning_seen_at" ] && grep -Eq "$WARNING_RE" "$LOG" 2>/dev/null; then
    warning_seen_at=$now
    echo "[WARN ] $TAG (selector-broken warning fired; arming watchdog ${STALL_SECONDS}s) @ $now"
  fi
  if [ -n "$warning_seen_at" ]; then
    since_growth=$(( now - last_growth_at ))
    if [ "$since_growth" -ge "$STALL_SECONDS" ]; then
      echo "[STUCK] $TAG (no news.csv growth for ${since_growth}s after warning; killing python) @ $now"
      kill_python
      stuck_triggered=1
      break
    fi
  fi
done

wait "$WRAP_PID" 2>/dev/null
STATUS=$?

if [ "$timeout_triggered" -eq 1 ]; then
  tail -3 "$LOG"
elif [ "$stuck_triggered" -eq 1 ]; then
  echo "[FAIL ] $TAG (WAF-watchdog killed; suspected false-CLEAR — DEFER) @ $(date +%s)"
  tail -3 "$LOG"
elif [ $STATUS -eq 0 ]; then
  echo "[DONE ] $TAG @ $(date +%s)"
else
  echo "[FAIL ] $TAG (exit $STATUS) @ $(date +%s)"
  tail -3 "$LOG"
fi

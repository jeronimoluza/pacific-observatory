#!/usr/bin/env bash
# Weekly Common Crawl sweep of newly onboarded sources, after the Monday onboarding.
# cron: 5 3 * * 1  setsid nohup bash <this file> </dev/null >/dev/null 2>&1
# Waits for STATUS_onboard to finish (polls; never takes monday.sh's lock, which it would
# then skip), then sweeps every stem in any week's new_sources.txt not yet in cc_swept.txt.
# Status: ~/po/logs/weekly/<YYYY-Www>/STATUS_cc; summary: cc/cc_summary.md; log: cc.log.
set -u
TREE=/home/jeronimoluza/po-worktrees/discovery-onboard
PY=/home/jeronimoluza/venv/bin/python
WEEKLY=/home/jeronimoluza/po/logs/weekly
WEEK=$(date -u +%G-W%V)
OUT=$WEEKLY/$WEEK
GATE_GB=${GATE_GB:-15}
mkdir -p "$OUT"
status() { echo "$(date -u +%FT%TZ) $*" | tee "$OUT/STATUS_cc" >>"$OUT/events.log"; }
free_gb() { df -BG --output=avail / | tail -1 | tr -dc 0-9; }

exec 7>"$OUT/.cc.lock"
flock -n 7 || exit 0

status "WAITING for onboarding (STATUS_onboard)"
for _ in $(seq 240); do
  grep -qE " (DONE|FAILED|BLOCKED)" "$OUT/STATUS_onboard" 2>/dev/null && break
  sleep 300
done

if [ "$(free_gb)" -lt "$GATE_GB" ]; then
  status "BLOCKED disk $(free_gb) GB free < gate $GATE_GB GB; CC sweep not started"
  exit 1
fi

cat "$WEEKLY"/*/new_sources.txt >"$OUT/cc_sources.txt" 2>/dev/null
if [ ! -s "$OUT/cc_sources.txt" ]; then
  status "DONE no new_sources.txt in any week; nothing to sweep"
  exit 0
fi

cd "$TREE/src" || { status "BLOCKED no tree $TREE"; exit 1; }
CLI=(env PO_CC_INDEX_DIR=/mnt/backup5tb/cc_index systemd-run --user --scope -q -p MemoryMax=6G
  "$PY" -c "import sys; sys.argv = ['po', 'prices', 'cc-weekly'] + sys.argv[1:]; from cli import main; main()")

# Fetch failures from earlier weeks are transient (503s, stalls): retry them first.
RETRY=()
for d in "$WEEKLY"/*/cc/misses; do
  [ -d "$d" ] && [ "$d" != "$OUT/cc/misses" ] && RETRY+=(--retry-misses "$d")
done
if [ ${#RETRY[@]} -gt 0 ] && [ -s "$WEEKLY/cc_swept.txt" ]; then
  status "RUNNING retry of earlier fetch failures"
  "${CLI[@]}" --sources "$WEEKLY/cc_swept.txt" "${RETRY[@]}" --reasons fetch_failed \
    --data-root /home/jeronimoluza/po/data/prices --work "$OUT/cc_retry" >"$OUT/cc_retry.log" 2>&1
fi
status "RUNNING cc-weekly @$(git rev-parse --short HEAD), log $OUT/cc.log"
"${CLI[@]}" --sources "$OUT/cc_sources.txt" --state "$WEEKLY/cc_swept.txt" \
  --data-root /home/jeronimoluza/po/data/prices --work "$OUT/cc" >"$OUT/cc.log" 2>&1
RC=$?
if [ "$RC" -eq 0 ]; then
  status "DONE $(tail -1 "$OUT/cc.log")"
else
  status "FAILED rc=$RC $(tail -1 "$OUT/cc.log"); see $OUT/cc.log and cc/cc_summary.md"
fi

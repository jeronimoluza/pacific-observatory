#!/usr/bin/env bash
# Weekly Monday collect (spec vault specs/prices-refactor/2026-09-28-weekly-run.md, step 4).
# Runs every configured source from ~/po-worktrees/refactor on branch weekly/<YYYY-Www>.
# cron: 0 6 * * 1  setsid nohup bash <this file> </dev/null >/dev/null 2>&1
# Status for the week lands in ~/po/logs/weekly/<YYYY-Www>/STATUS (one line, overwritten).
set -u
# cron has no login session: point systemd-run --user at the lingering user manager.
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
TREE=/home/jeronimoluza/po-worktrees/refactor
PY=/home/jeronimoluza/venv/bin/python
GATE_GB=${GATE_GB:-15}
FLOOR_GB=${FLOOR_GB:-3}
WEEK=$(date -u +%G-W%V)
OUT=/home/jeronimoluza/po/logs/weekly/$WEEK
mkdir -p "$OUT"
status() { echo "$(date -u +%FT%TZ) $*" | tee "$OUT/STATUS" >>"$OUT/events.log"; }
free_gb() { df -BG --output=avail / | tail -1 | tr -dc 0-9; }

exec 9>"$OUT/.collect.lock"
flock -n 9 || { echo "$(date -u +%FT%TZ) skipped: collect lock held" >>"$OUT/events.log"; exit 0; }

if [ "$(free_gb)" -lt "$GATE_GB" ]; then
  status "BLOCKED disk $(free_gb) GB free < gate $GATE_GB GB; collect not started"
  exit 1
fi

cd "$TREE" || { status "BLOCKED no tree $TREE"; exit 1; }
BRANCH=weekly/$WEEK
if [ "$(git branch --show-current)" != "$BRANCH" ]; then
  if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    status "BLOCKED $TREE has uncommitted changes; cannot switch to $BRANCH"
    exit 1
  fi
  git rev-parse --verify -q "$BRANCH" >/dev/null && git checkout -q "$BRANCH" || git checkout -q -b "$BRANCH"
fi

# Sources onboarded on prices/discovery-onboard (Monday 03:00) reach collect only through this copy:
# the branches have diverged, so a merge would drop spiders. Files already here are left alone.
# Prints the stems of the configs it copied.
ONB=prices/discovery-onboard
copy_onboarded() {
  local new
  new=$(git diff --name-only --diff-filter=A "$BRANCH...$ONB" -- src/prices/configs src/prices/price_scraping/spiders \
    | while read -r f; do git cat-file -e "HEAD:$f" 2>/dev/null || echo "$f"; done)
  [ -n "$new" ] || return 0
  # shellcheck disable=SC2086
  git checkout -q "$ONB" -- $new && git commit -q -m "feat(prices): bring onboarded sources onto $BRANCH" -- $new \
    || { echo "$(date -u +%FT%TZ) copy from $ONB failed" >>"$OUT/events.log"; return 0; }
  echo "$(date -u +%FT%TZ) copied $(echo "$new" | wc -l) onboarded files from $ONB" >>"$OUT/events.log"
  echo "$new" | sed -n "s|^src/prices/configs/.*/\([^/]*\)\.yaml$|\1|p"
}
copy_onboarded >/dev/null

TS=$(date -u +%Y%m%dT%H%MZ)
LOG=$TREE/logs/prices/collect_${WEEK}_$TS.log
status "RUNNING collect from $BRANCH @$(git rev-parse --short HEAD), log $LOG"

systemd-run --user --scope -q -p MemoryMax=16G -p MemorySwapMax=2G \
  "$PY" run.py prices collect -P 24 >"$LOG" 2>&1 &
PID=$!
echo "$PID" >"$OUT/collect.pid"

# Watchdog: stop the run before the root disk fills.
while kill -0 "$PID" 2>/dev/null; do
  if [ "$(free_gb)" -lt "$FLOOR_GB" ]; then
    status "ABORTED disk $(free_gb) GB free < floor $FLOOR_GB GB; collect stopped"
    pkill -TERM -P "$PID"; kill -TERM "$PID"
    break
  fi
  sleep 300
done
wait "$PID"; RC=$?

LEDGER=$(sed -n 's/.*ledger: \(.*status.jsonl\).*/\1/p' "$LOG" | tail -1)
SUMMARY=$(sed -n 's/.*Prices collect .* done: \(.*\)/\1/p' "$LOG" | tail -1)
echo "$LEDGER" >"$OUT/ledger_path"
case "$(cat "$OUT/STATUS")" in
  *ABORTED*) exit 1 ;;
esac

# Onboarding can still be committing when collect starts at 06:00. Wait for it (up to 6 h past the
# main run), then collect whatever it added after the first copy, so every source is collected on
# the Monday it is onboarded. STATUS stays RUNNING until this pass ends.
if [ -f "$OUT/STATUS_onboard" ]; then
  for _ in $(seq 72); do
    grep -qE " (DONE|FAILED|BLOCKED)" "$OUT/STATUS_onboard" && break
    sleep 300
  done
fi
LATE=$(copy_onboarded)
NLATE=0
if [ -n "$LATE" ]; then
  NLATE=$(echo "$LATE" | wc -l)
  echo "$LATE" >"$OUT/collect_late_sources.txt"
  mkdir -p "$OUT/collect_late"
  status "RUNNING late collect of $NLATE sources onboarded after the main run started"
  systemd-run --user --scope -q -p MemoryMax=12G -p MemorySwapMax=2G \
    xargs -P 4 -I{} sh -c "\"$PY\" run.py prices collect -s {} -P 2 --timeout 5400 >\"$OUT/collect_late/{}.log\" 2>&1" \
    <"$OUT/collect_late_sources.txt"
fi
NLATE_OK=$(grep -l "done:" "$OUT"/collect_late/*.log 2>/dev/null | wc -l)
status "DONE rc=$RC $SUMMARY ledger=$LEDGER late=$NLATE_OK/$NLATE free=$(free_gb)GB"

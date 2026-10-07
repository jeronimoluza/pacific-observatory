#!/usr/bin/env bash
# Weekly Monday collect (spec vault specs/prices-refactor/2026-09-28-weekly-run.md, step 4).
# Runs every configured source from ~/po-worktrees/refactor on branch weekly/<YYYY-Www>.
# cron: 0 6 * * 1  setsid nohup bash <this file> </dev/null >/dev/null 2>&1
# `collect.sh new`: the /weekly skill runs this once onboarding is done, to collect only the sources
# onboarded since the last copy, the same day. Own lock; status in STATUS_collect_new.
# Status for the week lands in ~/po/logs/weekly/<YYYY-Www>/STATUS (one line, overwritten).
set -u
# cron has no login session: point systemd-run --user at the lingering user manager.
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
TREE=/home/jeronimoluza/po-worktrees/refactor
PY=/home/jeronimoluza/venv/bin/python
GATE_GB=${GATE_GB:-15}
FLOOR_GB=${FLOOR_GB:-3}
WEEK=${WEEK:-$(date -u +%G-W%V)}
OUT=/home/jeronimoluza/po/logs/weekly/$WEEK
MODE=${1:-all}
mkdir -p "$OUT"
if [ "$MODE" = new ]; then STATUS_FILE=STATUS_collect_new; LOCK=.collect_new.lock; else STATUS_FILE=STATUS; LOCK=.collect.lock; fi
status() { echo "$(date -u +%FT%TZ) $*" | tee "$OUT/$STATUS_FILE" >>"$OUT/events.log"; }
free_gb() { df -BG --output=avail / | tail -1 | tr -dc 0-9; }

exec 9>"$OUT/$LOCK"
flock -n 9 || { echo "$(date -u +%FT%TZ) skipped: $LOCK held" >>"$OUT/events.log"; exit 0; }

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

# Sources onboarded on prices/discovery-onboard reach collect only through this copy: the branches
# have diverged, so a merge would drop spiders. Files already here are left alone.
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

if [ "$MODE" = new ]; then
  NEW=$(copy_onboarded)
  if [ -z "$NEW" ]; then
    status "DONE nothing new to collect"
    exit 0
  fi
  N=$(echo "$NEW" | wc -l)
  echo "$NEW" >>"$OUT/collect_new_sources.txt"
  mkdir -p "$OUT/collect_new"
  status "RUNNING collect of $N new sources from $BRANCH @$(git rev-parse --short HEAD)"
  # The lock guards the copy + commit above; collects of different sources can overlap, and
  # xargs children would otherwise inherit fd 9 and hold the lock for the whole collect.
  exec 9>&-
  # 6G: this can overlap the main collect (16G) on a8's 26 GB.
  echo "$NEW" | systemd-run --user --scope -q -p MemoryMax=6G -p MemorySwapMax=1G \
    xargs -P 4 -I{} sh -c "\"$PY\" run.py prices collect -s {} -P 2 --timeout 5400 >\"$OUT/collect_new/{}.log\" 2>&1"
  OK=$(echo "$NEW" | while read -r s; do grep -q "done:" "$OUT/collect_new/$s.log" 2>/dev/null && echo "$s"; done | wc -l)
  status "DONE $OK/$N new sources finished; logs $OUT/collect_new"
  exit 0
fi

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
  *ABORTED*) ;;
  *) status "DONE rc=$RC $SUMMARY ledger=$LEDGER free=$(free_gb)GB" ;;
esac

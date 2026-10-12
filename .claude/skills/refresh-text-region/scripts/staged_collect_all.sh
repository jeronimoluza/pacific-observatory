#!/bin/bash
# Staged collect of every region into one run dir, for a scheduled host (a8).
#
# Usage: staged_collect_all.sh            (from the repo root / worktree)
#
# Writes only new rows to $STAGING_ROOT/<run_id>/<region>/... using the
# per-region ledgers in $TEXT_STATE_DIR (default ~/text_state); the archive
# disk is never touched. Writes $STAGING_ROOT/<run_id>/STATUS.md, which the
# Mac-side skill reads before `po text merge`.
#
# Env: REGIONS (default "menaap sar eap ssa lac eca"), P (parallel sources,
#      default 24), CAP (seconds per source, default 300),
#      STAGING_ROOT (default ~/text_staging), MIN_FREE_GB (default 5).
set -u

REGIONS="${REGIONS:-menaap sar eap ssa lac eca}"
P="${P:-24}"
CAP="${CAP:-300}"
STAGING_ROOT="${STAGING_ROOT:-$HOME/text_staging}"
STATE_DIR="${TEXT_STATE_DIR:-$HOME/text_state}"
MIN_FREE_GB="${MIN_FREE_GB:-5}"
S="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$STAGING_ROOT"
exec 9> "$STAGING_ROOT/.lock"
flock -n 9 || { echo "another staged collect holds $STAGING_ROOT/.lock" >&2; exit 1; }

RUN_ID=$(date -u +%Y%m%dT%H%MZ)
export STAGING="$STAGING_ROOT/$RUN_ID"
mkdir -p "$STAGING"
STATUS="$STAGING/STATUS.md"
log() { echo "[$1] $(date -u +%FT%TZ) ${2:-}" | tee -a "$STAGING/driver.log"; }
free_gb() { df -Pk "$STAGING_ROOT" | awk 'NR==2 {print int($4 / 1048576)}'; }

{
  echo "# Staged collect $RUN_ID"
  echo
  echo "host: $(hostname)  commit: $(git rev-parse --short HEAD)  P=$P cap=${CAP}s"
  echo
  echo "| region | done | timeout | fail | stuck | sources with rows | news rows | note |"
  echo "|---|---|---|---|---|---|---|---|"
} > "$STATUS"

log RUN-START "$STAGING"
for r in $REGIONS; do
  if [ ! -s "$STATE_DIR/$r.sqlite" ]; then
    log SKIP "$r: no ledger at $STATE_DIR/$r.sqlite"
    echo "| $r | | | | | | | SKIPPED: no ledger |" >> "$STATUS"
    continue
  fi
  if [ "$(free_gb)" -lt "$MIN_FREE_GB" ]; then
    log ABORT "less than ${MIN_FREE_GB} GB free under $STAGING_ROOT"
    echo "| $r | | | | | | | ABORTED: disk below ${MIN_FREE_GB} GB |" >> "$STATUS"
    break
  fi
  log REGION-START "$r"
  bash "$S/launch_refresh.sh" "$r" "$P" "$CAP" > /dev/null
  until grep -q "REFRESH-DONE" "/tmp/refresh_${r}_nohup.log" 2>/dev/null; do sleep 60; done
  ev="/tmp/refresh_${r}_nohup.log"
  cp "$ev" "$STAGING/events_$r.log"
  read -r n_src n_rows < <(poetry run python -c "
import glob, sys, pandas
fs = glob.glob(sys.argv[1] + '/*/*/*/news.csv')
print(len(fs), sum(len(pandas.read_csv(f, usecols=['url'])) for f in fs))
" "$STAGING/$r")
  echo "| $r | $(grep -c '^\[DONE' "$ev") | $(grep -c '^\[TIMEOUT' "$ev") | $(grep -c '^\[FAIL' "$ev") | $(grep -c '^\[STUCK' "$ev") | $n_src | $n_rows | |" >> "$STATUS"
  log REGION-DONE "$r sources_with_rows=$n_src news_rows=$n_rows"
done
echo >> "$STATUS"
echo "free: $(free_gb) GB under $STAGING_ROOT" >> "$STATUS"
touch "$STAGING/.done"   # po text merge takes only finished runs
log RUN-DONE

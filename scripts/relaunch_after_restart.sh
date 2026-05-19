#!/usr/bin/env bash
# Re-launches all incomplete ECA scrapes after a PC restart.
# Uses DEFAULT mode (no --resume, no --rebuild) so each scrape:
#   1. Re-discovers URLs from listing → catches articles published since last run
#   2. Skips URLs already in news.csv (so existing data isn't re-fetched)
#   3. Adds the new ones
# This gives "continue where we left off + pick up daily new articles".
# (--resume would skip discovery and miss new articles — wrong for daily use.)
# Skips sources >=95% complete and an explicit DROP list of server-throttled
# state-news giants we've decided to leave alone.
#
# Usage:
#   bash scripts/relaunch_after_restart.sh           # launches all
#   MAX_JOBS=30 bash scripts/relaunch_after_restart.sh  # throttle parallelism
set -u
export PATH=/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$PATH
cd "$(dirname "$0")/.."

MAX_JOBS="${MAX_JOBS:-100}"   # near-unlimited by default — we have RAM
COVERAGE_THRESHOLD="${COVERAGE_THRESHOLD:-95}"   # skip sources >= this %
mkdir -p logs/rebuild
STATUS="logs/rebuild/_status_relaunch.tsv"
: > "$STATUS"

# DROP list — server-throttled or known-problematic. Don't relaunch.
# Edit this list if you want to revisit any of them.
DROP_SOURCES=(
  # Azerbaijan state news — server takes 3-8s per request, 100s of hours ETA
  "teleqraf" "report.az" "report.az_russian" "report.az_english"
)

is_dropped() {
  local s="$1"
  for d in "${DROP_SOURCES[@]}"; do
    [ "$s" = "$d" ] && return 0
  done
  return 1
}

# Build the relaunch list by inspecting each active YAML
echo "Computing relaunch list..." | tee logs/rebuild/_orchestrator_relaunch.log
LAUNCHED=0; SKIPPED_COMPLETE=0; SKIPPED_DROPPED=0; SKIPPED_NODATA=0

for yaml_path in src/text/configs/eca/*/*/*.yaml; do
  name=$(basename "$yaml_path")
  case "$name" in _0_*) continue ;; esac    # disabled
  parts=$(echo "$yaml_path" | tr '/' ' ')
  set -- $parts
  # path: src text configs eca SUBREGION COUNTRY SOURCE.yaml
  subregion=$(echo "$yaml_path" | awk -F/ '{print $(NF-2)}')
  country=$(echo "$yaml_path" | awk -F/ '{print $(NF-1)}')
  source="${name%.yaml}"

  if is_dropped "$source"; then
    SKIPPED_DROPPED=$((SKIPPED_DROPPED+1))
    continue
  fi

  csv="data/text/eca/$subregion/$country/$source/news.csv"
  urls="data/text/eca/$subregion/$country/$source/urls.csv"
  if [ ! -f "$csv" ]; then
    SKIPPED_NODATA=$((SKIPPED_NODATA+1))
    continue
  fi

  # Compute coverage
  news_n=$(tail -n +2 "$csv" 2>/dev/null | wc -l | tr -d ' ')
  urls_n=0
  [ -f "$urls" ] && urls_n=$(tail -n +2 "$urls" 2>/dev/null | wc -l | tr -d ' ')
  expected=$news_n
  [ "$urls_n" -gt "$expected" ] && expected=$urls_n
  if [ "$expected" -gt 0 ]; then
    cov=$(( news_n * 100 / expected ))
    if [ "$cov" -ge "$COVERAGE_THRESHOLD" ]; then
      SKIPPED_COMPLETE=$((SKIPPED_COMPLETE+1))
      continue
    fi
  fi

  # Launch with default mode — re-discovers + skips existing + picks up new
  while [ "$(jobs -rp | wc -l)" -ge "$MAX_JOBS" ]; do
    wait -n 2>/dev/null || true
  done
  LAUNCHED=$((LAUNCHED+1))
  slug="${source//\//_}"
  logf="logs/rebuild/relaunch_${country}_${slug}.log"
  echo "[$LAUNCHED] launching $country/$source (cov=${cov:-?}%)" >> logs/rebuild/_orchestrator_relaunch.log
  (
    start=$(date +%s)
    poetry run po text collect -c "$country" -s "$source" -y > "$logf" 2>&1
    rc=$?
    dur=$(( $(date +%s) - start ))
    printf '%s\t%s\t%s\t%d\t%d\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$country" "$source" "$rc" "$dur" >> "$STATUS"
  ) &
done

{
  echo "Relaunch summary:"
  echo "  Launched:           $LAUNCHED"
  echo "  Skipped (complete): $SKIPPED_COMPLETE  (>=${COVERAGE_THRESHOLD}% coverage)"
  echo "  Skipped (dropped):  $SKIPPED_DROPPED   (in DROP_SOURCES list)"
  echo "  Skipped (no data):  $SKIPPED_NODATA"
} | tee -a logs/rebuild/_orchestrator_relaunch.log

wait
echo "RELAUNCH ALL DONE at $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> logs/rebuild/_orchestrator_relaunch.log

#!/usr/bin/env bash
# Launches all remaining 76 sources simultaneously (no throttle).
# Coexists with the 60 already-orphaned scrapes running. Total peak: ~136.
set -u
export PATH=/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$PATH
cd "$(dirname "$0")/.."

STATUS="logs/rebuild/_status_atonce.tsv"
mkdir -p logs/rebuild
: > "$STATUS"

SOURCES_FILE=/tmp/remaining_entries.txt

run_one() {
  local tag="$1" country="$2" source="$3"
  local slug="${source//\//_}"
  local logf="logs/rebuild/${tag}_${country}_${slug}.log"
  local start=$(date +%s)
  poetry run po text collect -c "$country" -s "$source" --rebuild -y > "$logf" 2>&1
  local rc=$?
  local dur=$(( $(date +%s) - start ))
  printf '%s\t%s\t%s\t%s\t%d\t%d\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$tag" "$country" "$source" "$rc" "$dur" >> "$STATUS"
}

total=$(wc -l < "$SOURCES_FILE" | tr -d ' ')
echo "Starting at-once rebuild of $total sources (no throttle)" | tee -a logs/rebuild/_orchestrator_atonce.log
idx=0
while IFS='|' read -r tag country source; do
  idx=$((idx+1))
  echo "[$idx/$total] launching $tag/$country/$source" >> logs/rebuild/_orchestrator_atonce.log
  run_one "$tag" "$country" "$source" &
done < "$SOURCES_FILE"

wait
echo "ATONCE ALL DONE at $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> logs/rebuild/_orchestrator_atonce.log

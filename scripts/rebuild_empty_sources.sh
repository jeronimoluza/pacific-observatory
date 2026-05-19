#!/usr/bin/env bash
# Runs the 7 non-sitemap sources that came out empty after the earlier pkill
# interrupted mid-scrape. All configs have been verified (selectors match HTML,
# APIs respond). Just needs execution.
set -u
export PATH=/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$PATH
cd "$(dirname "$0")/.."

MAX_JOBS="${MAX_JOBS:-3}"
STATUS="logs/rebuild/_status_empty7.tsv"
mkdir -p logs/rebuild
: > "$STATUS"

# Ordered small-first so the long tail (aravot ~1.5M posts, sinteza ~164k) runs last.
SOURCES=(
  "ee|moldova|sinteza.md"
  "ee|ukraine|ekonomichna_pravda"
  "ca|kazakhstan|azh_russian"
  "ca|kyrgyz_republic|barometr"
  "ca|kyrgyz_republic|kyrtag_russian"
  "ca|turkmenistan|turkmenistan_gov"
  "so|armenia|aravot"
)

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

total="${#SOURCES[@]}"
echo "Starting empty-source rebuild of $total sources, MAX_JOBS=$MAX_JOBS" | tee -a logs/rebuild/_orchestrator_empty7.log
idx=0
for entry in "${SOURCES[@]}"; do
  IFS='|' read -r tag country source <<< "$entry"
  while [[ $(jobs -rp | wc -l) -ge $MAX_JOBS ]]; do
    wait -n 2>/dev/null || true
  done
  idx=$((idx+1))
  echo "[$idx/$total] launching $tag/$country/$source" >> logs/rebuild/_orchestrator_empty7.log
  run_one "$tag" "$country" "$source" &
done

wait
echo "EMPTY7 ALL DONE at $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> logs/rebuild/_orchestrator_empty7.log

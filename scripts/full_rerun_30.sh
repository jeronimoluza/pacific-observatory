#!/usr/bin/env bash
# Full re-runs (no --max-articles) for the 30 sources that passed the diagnostic test.
set -u
export PATH=/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$PATH
cd "$(dirname "$0")/.."

STATUS="logs/rebuild/_status_full_rerun.tsv"
mkdir -p logs/rebuild
printf 'ts\tcountry\tsource\trc\tdur_s\trows_after\n' > "$STATUS"

subregion_for() {
  case "$1" in
    kazakhstan|kyrgyz_republic|tajikistan|uzbekistan|turkmenistan) echo "central_asia" ;;
    bulgaria|poland|romania|croatia) echo "central_europe" ;;
    belarus|moldova|ukraine) echo "eastern_europe" ;;
    russian_federation) echo "russian_federation" ;;
    armenia|azerbaijan|georgia) echo "south_caucasus" ;;
    turkiye) echo "turkiye" ;;
    albania|bosnia_and_herzegovina|kosovo|montenegro|north_macedonia|serbia) echo "western_balkans" ;;
    *) echo "unknown" ;;
  esac
}

# 10 pagination OK + 20 small archive = 30 sources
SOURCES=(
  # OK (10)
  "romania|agerpres" "tajikistan|tajmigration" "kazakhstan|el_kz"
  "serbia|n1_serbia_english" "belarus|belarusian_partisan"
  "bosnia_and_herzegovina|balkan_insight_bih" "romania|digi24"
  "bulgaria|24chasa" "albania|voa_albanian" "bosnia_and_herzegovina|buka"
  # Small (20)
  "poland|wprost" "kyrgyz_republic|stan_kg" "russian_federation|tass_english"
  "north_macedonia|a1on" "bulgaria|bta_english" "kazakhstan|kp_kz"
  "bulgaria|capital.bg" "kosovo|gazeta_express" "bulgaria|webcafe"
  "albania|java_news" "kosovo|ekonomia_online" "montenegro|volim_podgoricu"
  "bulgaria|bnt" "georgia|apsny" "kosovo|indeks_online"
  "romania|gandul" "romania|romaniatv" "kosovo|insajderi"
  "albania|vizion_plus" "montenegro|in4s"
)

run_one() {
  local country="$1" source="$2"
  local sub=$(subregion_for "$country")
  local slug="${source//\//_}"
  local logf="logs/rebuild/full_${country}_${slug}.log"
  local csvf="data/text/eca/$sub/$country/$source/news.csv"
  local start=$(date +%s)
  poetry run po text collect -c "$country" -s "$source" --rebuild -y > "$logf" 2>&1
  local rc=$?
  local dur=$(( $(date +%s) - start ))
  local rows=0
  if [ -f "$csvf" ]; then
    rows=$(tail -n +2 "$csvf" 2>/dev/null | wc -l | tr -d ' ')
  fi
  printf '%s\t%s\t%s\t%d\t%d\t%d\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$country" "$source" "$rc" "$dur" "$rows" >> "$STATUS"
}

total="${#SOURCES[@]}"
echo "Full re-running $total verified-working sources" | tee logs/rebuild/_orchestrator_full_rerun.log
for entry in "${SOURCES[@]}"; do
  IFS='|' read -r country source <<< "$entry"
  run_one "$country" "$source" &
done
wait
echo "FULL RERUN ALL DONE at $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> logs/rebuild/_orchestrator_full_rerun.log

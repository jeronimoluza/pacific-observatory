#!/usr/bin/env bash
# Run each test config with --max-articles 50 to diagnose pagination/selector health.
set -u
export PATH=/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$PATH
cd "$(dirname "$0")/.."

STATUS="logs/rebuild/_status_diagnose.tsv"
mkdir -p logs/rebuild
printf 'ts\tcountry\tsource\trc\tdur_s\trows_after\n' > "$STATUS"

# Function to find subregion for a country
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

SOURCES=(
  "kazakhstan|el_kz" "kazakhstan|kp_kz"
  "kyrgyz_republic|stan_kg"
  "tajikistan|tajmigration"
  "uzbekistan|darakchi.uz"
  "bulgaria|24chasa" "bulgaria|bnt" "bulgaria|bta_english" "bulgaria|capital.bg" "bulgaria|webcafe"
  "poland|rzeczpospolita" "poland|tvrepublika" "poland|wprost"
  "romania|agerpres" "romania|digi24" "romania|gandul" "romania|romaniatv"
  "belarus|belarusian_partisan"
  "moldova|basarabia.md"
  "russian_federation|tass_english"
  "georgia|apsny"
  "turkiye|hurriyet"
  "albania|java_news" "albania|koha_jone" "albania|opinion" "albania|sot"
  "albania|vizion_plus" "albania|voa_albanian"
  "bosnia_and_herzegovina|balkan_insight_bih" "bosnia_and_herzegovina|buka"
  "kosovo|ekonomia_online" "kosovo|epokaere" "kosovo|gazeta_express"
  "kosovo|indeks_online" "kosovo|insajderi" "kosovo|klankosova" "kosovo|lajmi"
  "montenegro|in4s" "montenegro|volim_podgoricu"
  "north_macedonia|a1on"
  "serbia|krik_english" "serbia|n1_serbia_english"
)

run_one() {
  local country="$1" source="$2"
  local sub=$(subregion_for "$country")
  local slug="${source//\//_}"
  local logf="logs/rebuild/diag_${country}_${slug}.log"
  local csvf="data/text/eca/$sub/$country/$source/news.csv"
  local start=$(date +%s)
  poetry run po text collect -c "$country" -s "$source" --rebuild -y --max-articles 50 > "$logf" 2>&1
  local rc=$?
  local dur=$(( $(date +%s) - start ))
  local rows=0
  if [ -f "$csvf" ]; then
    rows=$(tail -n +2 "$csvf" 2>/dev/null | wc -l | tr -d ' ')
  fi
  printf '%s\t%s\t%s\t%d\t%d\t%d\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$country" "$source" "$rc" "$dur" "$rows" >> "$STATUS"
}

total="${#SOURCES[@]}"
echo "Diagnosing $total test configs (--max-articles 50 each)" | tee logs/rebuild/_orchestrator_diagnose.log
for entry in "${SOURCES[@]}"; do
  IFS='|' read -r country source <<< "$entry"
  run_one "$country" "$source" &
done
wait
echo "DIAGNOSE ALL DONE at $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> logs/rebuild/_orchestrator_diagnose.log

#!/usr/bin/env bash
# Re-runs the 42 "test" configs (1-99 rows) to see which grow vs stay tiny.
# Tiny ones after re-run are either broken selectors or genuinely small sites.
set -u
export PATH=/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$PATH
cd "$(dirname "$0")/.."

STATUS="logs/rebuild/_status_test_retry.tsv"
mkdir -p logs/rebuild
: > "$STATUS"

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
  local slug="${source//\//_}"
  local logf="logs/rebuild/test_retry_${country}_${slug}.log"
  local start=$(date +%s)
  poetry run po text collect -c "$country" -s "$source" --rebuild -y > "$logf" 2>&1
  local rc=$?
  local dur=$(( $(date +%s) - start ))
  printf '%s\t%s\t%s\t%d\t%d\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$country" "$source" "$rc" "$dur" >> "$STATUS"
}

total="${#SOURCES[@]}"
echo "Retrying $total test configs in parallel" | tee -a logs/rebuild/_orchestrator_test_retry.log
for entry in "${SOURCES[@]}"; do
  IFS='|' read -r country source <<< "$entry"
  echo "[$(date +%H:%M:%S)] launching $country/$source" >> logs/rebuild/_orchestrator_test_retry.log
  run_one "$country" "$source" &
done

wait
echo "TEST RETRY ALL DONE at $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> logs/rebuild/_orchestrator_test_retry.log

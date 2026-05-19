#!/usr/bin/env bash
# Re-launches the 28 scrapes that failed during the 09:40–09:51 UTC DNS blip
# on 2026-04-23. Sites are verified reachable now (all HTTP 200).
set -u
export PATH=/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$PATH
cd "$(dirname "$0")/.."

STATUS="logs/rebuild/_status_dns_retry.tsv"
mkdir -p logs/rebuild
: > "$STATUS"

# Format: country|source
SOURCES=(
  # Central Europe (15)
  "poland|dziennik.pl" "poland|fakt" "poland|gazeta.pl" "poland|interia" "poland|krytyka_polityczna"
  "romania|europa_fm" "romania|g4media" "romania|libertatea" "romania|mediafax"
  "bulgaria|glasove" "bulgaria|investor" "bulgaria|mediapool"
  "croatia|hrt" "croatia|jutarnji_list" "croatia|lider"
  # Russian Federation (4)
  "russian_federation|fontanka" "russian_federation|kommersant"
  "russian_federation|mediazona" "russian_federation|mk"
  # Türkiye (3)
  "turkiye|gercek_gundem" "turkiye|halktv" "turkiye|hurriyet"
  # Western Balkans (5)
  "bosnia_and_herzegovina|federalna"
  "kosovo|gazeta_express" "kosovo|kosovapress"
  "serbia|krik" "serbia|krik_english"
  # Belarus (1) — svaboda, also has fixed YAML from earlier
  "belarus|svaboda"
)

run_one() {
  local country="$1" source="$2"
  local slug="${source//\//_}"
  local logf="logs/rebuild/retry_${country}_${slug}.log"
  local start=$(date +%s)
  poetry run po text collect -c "$country" -s "$source" --rebuild -y > "$logf" 2>&1
  local rc=$?
  local dur=$(( $(date +%s) - start ))
  printf '%s\t%s\t%s\t%d\t%d\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$country" "$source" "$rc" "$dur" >> "$STATUS"
}

total="${#SOURCES[@]}"
echo "Retrying $total DNS-failed scrapes in parallel" | tee -a logs/rebuild/_orchestrator_dns_retry.log
for entry in "${SOURCES[@]}"; do
  IFS='|' read -r country source <<< "$entry"
  echo "[$(date +%H:%M:%S)] launching $country/$source" >> logs/rebuild/_orchestrator_dns_retry.log
  run_one "$country" "$source" &
done

wait
echo "DNS RETRY ALL DONE at $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> logs/rebuild/_orchestrator_dns_retry.log

#!/usr/bin/env bash
# Rebuilds all 148 sitemap-based configs after the title-extraction pipeline patch.
# Runs with controlled parallelism (MAX_JOBS concurrent scrapes) and writes per-source
# logs to logs/rebuild/<region>_<source>.log plus a status ledger at
# logs/rebuild/_status.tsv (appended on each completion: ts\tregion\tcountry\tsource\trc\tdur).
set -u
export PATH=/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$PATH
cd "$(dirname "$0")/.."

MAX_JOBS="${MAX_JOBS:-10}"
STATUS="logs/rebuild/_status.tsv"
mkdir -p logs/rebuild
: > "$STATUS"

# Format: subregion_tag|country|source
SOURCES=(
  # ---- Eastern Europe (32) ----
  "ee|belarus|belta" "ee|belarus|novychas" "ee|belarus|mlyn"
  "ee|belarus|zviazda" "ee|belarus|mogilevnews" "ee|belarus|belapan"
  "ee|belarus|neg" "ee|belarus|vb" "ee|belarus|svaboda"
  "ee|belarus|nasha_niva" "ee|belarus|charter97" "ee|belarus|belarusian_partisan"
  "ee|belarus|sb"
  "ee|ukraine|24tv.ua" "ee|ukraine|unian" "ee|ukraine|espreso"
  "ee|ukraine|zn.ua" "ee|ukraine|nv.ua_english" "ee|ukraine|texty.org.ua"
  "ee|ukraine|ukrinform" "ee|ukraine|focus.ua" "ee|ukraine|ukrinform_english"
  "ee|ukraine|interfax_ukraine" "ee|ukraine|censor.net" "ee|ukraine|nv.ua"
  "ee|ukraine|hromadske" "ee|ukraine|rbc-ukraine"
  "ee|moldova|protv.md" "ee|moldova|europalibera_moldova" "ee|moldova|basarabia.md"
  "ee|moldova|moldpres" "ee|moldova|moldpres_english"
  # ---- South Caucasus (40) ----
  "sc|armenia|pastinfo_english" "sc|armenia|pastinfo" "sc|armenia|168am"
  "sc|armenia|1in_am" "sc|armenia|factor" "sc|armenia|azatutyun"
  "sc|azerbaijan|turan" "sc|azerbaijan|apa_russian" "sc|azerbaijan|report.az"
  "sc|azerbaijan|qafqazinfo" "sc|azerbaijan|report.az_english" "sc|azerbaijan|1news_az"
  "sc|azerbaijan|eurasianet" "sc|azerbaijan|azertag_english" "sc|azerbaijan|trend_english"
  "sc|azerbaijan|azadliq" "sc|azerbaijan|axar" "sc|azerbaijan|teleqraf"
  "sc|azerbaijan|apa" "sc|azerbaijan|trend_russian" "sc|azerbaijan|bakupost"
  "sc|azerbaijan|news_az" "sc|azerbaijan|musavat" "sc|azerbaijan|report.az_russian"
  "sc|azerbaijan|azertag_russian" "sc|azerbaijan|trend" "sc|azerbaijan|azertag"
  "sc|azerbaijan|vzglyad" "sc|azerbaijan|apa_english"
  "sc|georgia|itv" "sc|georgia|oc_media" "sc|georgia|caucasuswatch"
  "sc|georgia|apsny" "sc|georgia|imedinews" "sc|georgia|publika"
  "sc|georgia|radiotavisupleba" "sc|georgia|sova_news" "sc|georgia|palitravideo"
  "sc|georgia|kvirispalitra" "sc|georgia|allnews"
  # ---- Central Asia (76) ----
  "ca|tajikistan|nm" "ca|tajikistan|ozodagon" "ca|tajikistan|ozodi"
  "ca|tajikistan|dialog" "ca|tajikistan|sputnik"
  "ca|turkmenistan|gundogar" "ca|turkmenistan|turkmenportal_russian"
  "ca|turkmenistan|turkmenportal_english" "ca|turkmenistan|azathabar"
  "ca|turkmenistan|turkmenportal"
  "ca|kyrgyz_republic|stan_kg" "ca|kyrgyz_republic|24kg_english"
  "ca|kyrgyz_republic|vesti_kg" "ca|kyrgyz_republic|gazeta_kg"
  "ca|kyrgyz_republic|open_kg" "ca|kyrgyz_republic|vesti_kg_russian"
  "ca|kyrgyz_republic|akchabar" "ca|kyrgyz_republic|bulak"
  "ca|kyrgyz_republic|economist.kg" "ca|kyrgyz_republic|sputnik"
  "ca|kyrgyz_republic|24kg" "ca|kyrgyz_republic|azattyk"
  "ca|kyrgyz_republic|kaktus_media" "ca|kyrgyz_republic|24kg_russian"
  "ca|uzbekistan|gazeta.uz" "ca|uzbekistan|upl.uz" "ca|uzbekistan|uza.uz_english"
  "ca|uzbekistan|gazeta.uz_english" "ca|uzbekistan|qalampir.uz"
  "ca|uzbekistan|darakchi.uz_russian" "ca|uzbekistan|sputniknews.uz"
  "ca|uzbekistan|daryo.uz_russian" "ca|uzbekistan|norma.uz"
  "ca|uzbekistan|repost.uz" "ca|uzbekistan|zamin.uz" "ca|uzbekistan|review.uz"
  "ca|uzbekistan|daryo.uz" "ca|uzbekistan|gazeta.uz_russian"
  "ca|uzbekistan|spot.uz_russian" "ca|uzbekistan|12news.uz"
  "ca|uzbekistan|uza.uz_russian" "ca|uzbekistan|darakchi.uz"
  "ca|uzbekistan|uza.uz" "ca|uzbekistan|yuz.uz" "ca|uzbekistan|spot.uz"
  "ca|kazakhstan|365info" "ca|kazakhstan|azattyq_rferl" "ca|kazakhstan|liter_kz"
  "ca|kazakhstan|24kz_russian" "ca|kazakhstan|el_kz" "ca|kazakhstan|inbusiness_kz"
  "ca|kazakhstan|nur.kz" "ca|kazakhstan|tengrinews_russian" "ca|kazakhstan|24kz"
  "ca|kazakhstan|forbes_kz" "ca|kazakhstan|informburo" "ca|kazakhstan|exclusive_kz"
  "ca|kazakhstan|aqparat" "ca|kazakhstan|stan_kz" "ca|kazakhstan|zakon.kz"
  "ca|kazakhstan|adyrna_russian" "ca|kazakhstan|mediazona_ca" "ca|kazakhstan|caravan_kz"
  "ca|kazakhstan|kazinform_english" "ca|kazakhstan|baq_kz_russian" "ca|kazakhstan|vecher_kz"
  "ca|kazakhstan|adyrna" "ca|kazakhstan|tengrinews" "ca|kazakhstan|the_astana_times"
  "ca|kazakhstan|kazakhstan_today" "ca|kazakhstan|kp_kz" "ca|kazakhstan|qazaqstan_tv"
  "ca|kazakhstan|ult_kz" "ca|kazakhstan|azh" "ca|kazakhstan|vlast.kz"
  "ca|kazakhstan|kapital.kz"
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
echo "Starting rebuild of $total sources, MAX_JOBS=$MAX_JOBS" | tee -a logs/rebuild/_orchestrator.log
idx=0
for entry in "${SOURCES[@]}"; do
  IFS='|' read -r tag country source <<< "$entry"
  # Throttle: block while we have MAX_JOBS running
  while [[ $(jobs -rp | wc -l) -ge $MAX_JOBS ]]; do
    wait -n 2>/dev/null || true
  done
  idx=$((idx+1))
  echo "[$idx/$total] launching $tag/$country/$source" >> logs/rebuild/_orchestrator.log
  run_one "$tag" "$country" "$source" &
done

# Drain
wait
echo "ALL DONE at $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> logs/rebuild/_orchestrator.log

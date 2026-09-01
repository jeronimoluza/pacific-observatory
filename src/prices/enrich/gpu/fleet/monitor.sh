#!/usr/bin/env bash
# Per-pod liveness, bucket counts written so far, and the last log line.
#   ./monitor.sh            once
#   watch -n60 ./monitor.sh loop
source "$(dirname "$0")/lib.sh"

printf '%-7s %-9s %-26s %s\n' POD STATE BUCKETS LAST
pods | while read -r id host port lo hi; do
  n=$(remote_running "$host" "$port" || echo 0)
  state=$([ "${n:-0}" -gt 0 ] 2>/dev/null && echo running || echo STOPPED)
  counts=$(pssh "$host" "$port" "
    for t in \$(echo $MODELS | tr ',' ' '); do
      c=\$(ls $REMOTE_REPO/data/prices/enrich/_embed_store/\$t/*.npz 2>/dev/null | wc -l)
      printf '%s=%s ' \"\${t%%_bf16}\" \"\$c\"
    done" || echo -)
  last=$(pssh "$host" "$port" "tail -1 $REMOTE_LOG/$id.log 2>/dev/null" || echo -)
  printf '%-7s %-9s %-26s %s\n' "$id" "$state" "$counts" "${last:0:70}"
done

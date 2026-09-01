#!/usr/bin/env bash
# Report whether every pod is provisioned and what it is doing.
#   ./check.sh
source "$(dirname "$0")/lib.sh"

printf '%-7s %-22s %-9s %-8s %-7s %s\n' POD HOST GPU VENV DRIVER STATE
pods | while read -r id host port lo hi; do
  gpu=$(pssh "$host" "$port" "nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1" || echo -)
  venv=$(pssh "$host" "$port" "test -x $REMOTE_VENV/bin/python && echo ok || echo MISSING")
  drv=$(pssh "$host" "$port" "test -f $REMOTE_REPO/src/prices/enrich/gpu/gpu_embed_bf16.py && echo ok || echo MISSING")
  # `grep -c ... || echo 0` prints "0\n0": grep -c prints 0 AND exits 1, so the
  # fallback fires on top of the printed zero. A dead process then reads as alive.
  n=$(pssh "$host" "$port" "pgrep -f gpu_embed_bf16.py | wc -l" || echo 0)
  state=$([ "${n:-0}" -gt 0 ] 2>/dev/null && echo "running($n)" || echo idle)
  printf '%-7s %-22s %-9s %-8s %-7s %s\n' "$id" "$host:$port" "${gpu:0:9}" "$venv" "$drv" "$state"
done

#!/usr/bin/env bash
# Start the embed on every pod over its own bucket range, then return.
#   ./launch.sh
source "$(dirname "$0")/lib.sh"

pods | while read -r id host port lo hi; do
  echo "launching $id: buckets $lo-$hi ($MODELS)"
  # setsid + </dev/null + &: a plain nohup'd remote process still holds the ssh
  # session open, which blocked the original launch.sh after pod2 and left pods
  # 3-6 never started.
  pssh "$host" "$port" "
    cd $REMOTE_REPO &&
    mkdir -p $REMOTE_LOG &&
    setsid nohup env PYTHONPATH=src HF_HOME=/workspace/hf \
      EMBED_UNIVERSE=${EMBED_UNIVERSE:-data/prices/_enrich/transfer/embed_universe_cc_20260901.parquet} \
      $REMOTE_VENV/bin/python src/prices/enrich/gpu/gpu_embed_bf16.py \
        --models $MODELS --bucket-lo $lo --bucket-hi $hi \
      > $REMOTE_LOG/$id.log 2>&1 < /dev/null &
    sleep 1; echo '$id started'
  " &
done
wait
echo "all launches dispatched -- ./monitor.sh for progress"

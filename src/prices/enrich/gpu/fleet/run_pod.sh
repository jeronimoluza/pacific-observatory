#!/usr/bin/env bash
# One pod end to end: setup -> launch -> wait for ALL BLOCKS DONE -> pull -> verify sha.
#   PODS_FILE=<work>/pods.txt KIT=<kit.tar.gz> UNIVERSE_NAME=<universe file in the kit> \
#   DEST=<local delta store> ./run_pod.sh pod1
# Run one per pod on a8 under systemd-run (--user --collect -p MemoryMax=2G).
# The result is a FILE per pod, not the unit's liveness: <work>/finish/READY_<id> or
# BAD_<id>. A pod may be deleted only after its READY_<id> exists.
source "$(dirname "$0")/lib.sh"

id="${1:-}"
[ -n "$id" ] || die "usage: run_pod.sh <pod id from $PODS_FILE>"
KIT="${KIT:-}"; DEST="${DEST:-}"; UNIVERSE_NAME="${UNIVERSE_NAME:-}"
[ -f "$KIT" ] && [ -n "$DEST" ] && [ -n "$UNIVERSE_NAME" ] || die "set KIT, DEST and UNIVERSE_NAME"
read -r _ host port lo hi < <(pods | awk -v id="$id" '$1 == id')
[ -n "${hi:-}" ] || die "$id not in $PODS_FILE"
M="$(dirname "$PODS_FILE")/finish"; mkdir -p "$M"
UNIVERSE="data/prices/_enrich/transfer/$UNIVERSE_NAME"
SSH_OPTS="$SSH_OPTS -o ServerAliveInterval=30"

echo "$id setup $(date -u +%T)"
scp $SSH_OPTS -P "$port" "$KIT" "root@$host:/workspace/pod_kit.tar.gz" || { echo "$id scp failed" > "$M/BAD_$id"; exit 1; }
pssh "$host" "$port" "
  set -e
  mkdir -p $REMOTE_REPO $REMOTE_LOG /workspace/hf
  export HF_HOME=/workspace/hf HF_HUB_ENABLE_HF_TRANSFER=1
  test -x $REMOTE_VENV/bin/python || python -m venv --system-site-packages $REMOTE_VENV
  $REMOTE_VENV/bin/pip -q install -U sentence-transformers transformers huggingface_hub hf_transfer pyarrow numpy python-dotenv
  tar xzf /workspace/pod_kit.tar.gz -C /workspace --no-same-owner
  for m in Qwen/Qwen3-Embedding-8B Qwen/Qwen3-Embedding-4B Snowflake/snowflake-arctic-embed-l-v2.0; do
    $REMOTE_VENV/bin/hf download \"\$m\" --exclude '*.pth' --exclude '*.onnx' --exclude '*.gguf' >/dev/null
  done
  echo PROVISIONED
" || { echo "$id setup failed" > "$M/BAD_$id"; exit 1; }

# ssh -f: W42 launched with plain `ssh -n ... setsid nohup ... &` and on 2 of 3 pods
# the session never returned, so the wait below never started (20 idle GPU minutes).
echo "$id launch buckets $lo-$hi $(date -u +%T)"
ssh -f -n $SSH_OPTS -p "$port" "root@$host" "
  cd $REMOTE_REPO && mkdir -p $REMOTE_LOG &&
  setsid nohup env PYTHONPATH=src HF_HOME=/workspace/hf EMBED_UNIVERSE=$UNIVERSE \
    $REMOTE_VENV/bin/python src/prices/enrich/gpu/gpu_embed_bf16.py \
      --models $MODELS --bucket-lo $lo --bucket-hi $hi \
    > $REMOTE_LOG/$id.log 2>&1 < /dev/null &"
sleep 20
[ "$(remote_running "$host" "$port")" -gt 0 ] 2>/dev/null || { echo "$id driver did not start" > "$M/BAD_$id"; exit 1; }

while :; do
  s=$(pssh "$host" "$port" "grep -c 'ALL BLOCKS DONE' $REMOTE_LOG/$id.log; grep -cE 'FAILED|stopped cleanly|Traceback' $REMOTE_LOG/$id.log; ps -eo args | grep -c '[g]pu_embed_bf16.py'" 2>/dev/null | tr '\n' ' ')
  set -- $s
  [ "${1:-}" = 1 ] && [ "${3:-}" = 0 ] && break
  [ -n "${2:-}" ] && [ "$2" != 0 ] && { echo "$id driver error: $s" > "$M/BAD_$id"; exit 1; }
  [ -n "${3:-}" ] && [ "$3" = 0 ] && [ "$1" = 0 ] && { echo "$id driver gone without DONE: $s" > "$M/BAD_$id"; exit 1; }
  sleep 120
done

echo "$id done on pod $(date -u +%T), final pull" > "$M/log_$id"
for tag in $(echo "$MODELS" | tr ',' ' '); do
  for try in 1 2 3; do
    rsync -rt --exclude '*.tmp' -e "ssh $SSH_OPTS -p $port" \
      "root@$host:$REMOTE_REPO/data/prices/enrich/_embed_store/$tag/" "$DEST/$tag/" && break
  done
done
scp $SSH_OPTS -P "$port" "$FLEET_DIR/verify_pod.py" "root@$host:/workspace/verify_pod.py" >/dev/null
pssh "$host" "$port" "cd $REMOTE_REPO && $REMOTE_VENV/bin/python /workspace/verify_pod.py $UNIVERSE $lo $hi" > "$M/manifest_$id.txt" 2>&1
nb=0
while read -r tag b n sha st; do
  [ "$tag" = SUMMARY ] && continue
  f="$DEST/$tag/$(printf 'bucket_%03d.npz' "$b")"
  l=$(sha256sum "$f" 2>/dev/null | cut -d' ' -f1)
  [ "$st" = OK ] && [ "$l" = "$sha" ] || { nb=$((nb + 1)); echo "mismatch $tag $b pod=$st local=${l:0:12} remote=${sha:0:12}" >> "$M/log_$id"; }
done < "$M/manifest_$id.txt"
ntags=$(echo "$MODELS" | tr ',' '\n' | wc -l)
rows=$(grep -vc SUMMARY "$M/manifest_$id.txt"); exp=$((ntags * (hi - lo + 1)))
echo "$id rows=$rows/$exp local_mismatch=$nb $(grep SUMMARY "$M/manifest_$id.txt") $(date -u +%T)" >> "$M/log_$id"
if [ "$rows" = "$exp" ] && [ "$nb" = 0 ] && grep -q "bad 0$" "$M/manifest_$id.txt"; then
  cp "$M/log_$id" "$M/READY_$id"
else
  cp "$M/log_$id" "$M/BAD_$id"; exit 1
fi

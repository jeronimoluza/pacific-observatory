#!/usr/bin/env bash
# Provision every pod: venv on container disk, deps, model weights, repo payload.
#   ./setup.sh /path/to/pod_kit.tar.gz
# Re-runnable; skips work already done. ~3 min per pod against a warm HF cache.
source "$(dirname "$0")/lib.sh"

KIT="${1:-}"
[ -f "$KIT" ] || die "usage: ./setup.sh <pod_kit.tar.gz>"

pods | while read -r id host port lo hi; do
  echo "=== $id ($host:$port) ==="
  scp $SSH_OPTS -P "$port" "$KIT" "root@$host:/workspace/pod_kit.tar.gz" || { echo "$id: scp FAILED"; continue; }
  # --system-site-packages so torch comes from the base image rather than pip.
  # HF_HOME on /workspace keeps the ~33GB weight cache across pod recreation.
  pssh "$host" "$port" "
    set -e
    mkdir -p $REMOTE_REPO $REMOTE_LOG /workspace/hf
    export HF_HOME=/workspace/hf
    test -x $REMOTE_VENV/bin/python || python -m venv --system-site-packages $REMOTE_VENV
    $REMOTE_VENV/bin/pip -q install -U sentence-transformers transformers huggingface_hub pyarrow numpy
    tar xzf /workspace/pod_kit.tar.gz -C /workspace
    # One --exclude per flag. Multi-arg --exclude makes hf download fetch NOTHING,
    # silently, and the failure only shows up as a fp32 OOM much later.
    for m in Qwen/Qwen3-Embedding-8B Qwen/Qwen3-Embedding-4B Snowflake/snowflake-arctic-embed-l-v2.0; do
      $REMOTE_VENV/bin/hf download \"\$m\" --exclude '*.pth' --exclude '*.onnx' --exclude '*.gguf' >/dev/null
    done
    echo '$id provisioned'
  " || echo "$id: setup FAILED"
done

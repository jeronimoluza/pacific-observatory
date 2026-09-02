#!/usr/bin/env bash
# Pull completed bucket files off every pod into one store on DEST.
#   DEST=user@geekom:/data/embed_store ./download.sh          one pass
#   DEST=... ./download.sh --loop 900                         every 15 min until all pods stop
#
# Safe to run mid-flight: bucket writes are atomic (.npz.tmp -> rename), so any
# bucket_NNN.npz that is visible is complete. Running a loop alongside the GPUs
# finishes the transfer within minutes of the last batch instead of after it.
# NOTE: pods 2..N use pod-local volumes that die with the pod -- no pod may be
# terminated before its slice is downloaded and verified.
source "$(dirname "$0")/lib.sh"

DEST="${DEST:-}"
STREAMS="${STREAMS:-2}"
[ -n "$DEST" ] || die "set DEST=user@host:/path/to/embed_store"

LOOP=0
[ "${1:-}" = "--loop" ] && LOOP="${2:-900}"

one_pass() {
  local work
  work=$(mktemp -d)
  pods | while read -r id host port lo hi; do
    for tag in $(echo "$MODELS" | tr ',' ' '); do
      # Stripe this pod's bucket range across STREAMS parallel rsyncs. One stream
      # per pod leaves the link idle; the ceiling is server-side, not bandwidth.
      for s in $(seq 0 $((STREAMS - 1))); do
        list="$work/$id.$tag.$s"
        for b in $(seq "$lo" "$hi"); do
          [ $(( (b - lo) % STREAMS )) -eq "$s" ] && printf 'bucket_%03d.npz\n' "$b"
        done > "$list"
        rsync -a --ignore-missing-args --files-from="$list" \
          -e "ssh $SSH_OPTS -p $port" \
          "root@$host:$REMOTE_REPO/data/prices/enrich/_embed_store/$tag/" \
          "$DEST/$tag/" 2>/dev/null &
      done
    done
  done
  wait
  rm -rf "$work"
}

while :; do
  echo "=== pass $(date -u +%FT%TZ) ==="
  one_pass
  [ "$LOOP" = 0 ] && break
  live=$(pods | while read -r id host port lo hi; do
           remote_running "$host" "$port"; done | awk '{s += $1} END {print s + 0}')
  [ "${live:-0}" -eq 0 ] && { echo "all pods idle; final pass done"; break; }
  sleep "$LOOP"
done

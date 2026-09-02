# Shared fleet helpers. Sourced, never executed.
#
# pods.txt is the plan emitted by plan.py with HOST/PORT filled in:
#   pod1<TAB>1.2.3.4<TAB>12345<TAB>0<TAB>21
# Lines starting with # and blank lines are ignored.

set -uo pipefail

FLEET_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PODS_FILE="${PODS_FILE:-$FLEET_DIR/pods.txt}"
REMOTE_REPO="${REMOTE_REPO:-/workspace/repo}"
REMOTE_VENV="${REMOTE_VENV:-/root/venv}"   # container disk: the /workspace venv is a broken stub
REMOTE_LOG="${REMOTE_LOG:-/workspace/logs}"
MODELS="${MODELS:-8b_bf16,4b_bf16,arctic_bf16}"   # 0p6b carries weight zero in the ensemble
SSH_OPTS="${SSH_OPTS:--o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=15}"

die() { echo "ERROR: $*" >&2; exit 1; }

[ -f "$PODS_FILE" ] || die "no pods file at $PODS_FILE (run plan.py, then fill in HOST/PORT)"

# Emit "id host port lo hi" per pod, validating the file first.
pods() {
  local n=0
  while read -r id host port lo hi; do
    case "$id" in ''|'#'*) continue;; esac
    [ -n "${hi:-}" ] || die "malformed line in $PODS_FILE: $id $host $port $lo $hi"
    [ "$host" != HOST ] || die "$PODS_FILE still has placeholder HOST/PORT for $id"
    echo "$id $host $port $lo $hi"
    n=$((n + 1))
  done < "$PODS_FILE"
  [ "$n" -gt 0 ] || die "no pods in $PODS_FILE"
}

# ssh -n: without it, a command inside `while read` eats the loop's stdin and the
# loop runs exactly once instead of once per pod.
pssh() { local host="$1" port="$2"; shift 2; ssh -n $SSH_OPTS -p "$port" "root@$host" "$@"; }

# Count live embed processes on a pod.
#
# `pgrep -f gpu_embed_bf16.py` run over ssh matches the SSH command line ITSELF,
# so a dead process reports as alive -- the same inversion as the old
# `grep -c ... || echo 0`, just relocated. The `[g]` class is what breaks it: the
# remote cmdline contains the literal "[g]pu_embed_bf16", which the regex
# "[g]pu_embed_bf16" does not match, so neither the grep nor the ssh command
# counts itself.
remote_running() {
  pssh "$1" "$2" 'ps -eo args | grep -c "[g]pu_embed_bf16" || true'
}

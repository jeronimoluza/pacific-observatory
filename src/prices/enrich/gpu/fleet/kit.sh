#!/usr/bin/env bash
# Build the pod kit from the repo, not from copies: src/ at HEAD plus the universe.
#   ./kit.sh <universe.parquet> <out.tar.gz>
# Unpacks on the pod as /workspace/repo/{src,data/prices/_enrich/transfer/<universe>}.
set -euo pipefail
U="${1:-}"; OUT="${2:-}"
[ -f "$U" ] && [ -n "$OUT" ] || { echo "usage: kit.sh <universe.parquet> <out.tar.gz>" >&2; exit 1; }
[ -e "$OUT" ] && { echo "refusing to overwrite $OUT" >&2; exit 1; }
REPO=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/repo/data/prices/_enrich/transfer"
git -C "$REPO" archive --prefix=repo/ HEAD src | tar x -C "$T"
cp "$U" "$T/repo/data/prices/_enrich/transfer/"
tar czf "$OUT" -C "$T" repo
echo "kit $OUT @$(git -C "$REPO" rev-parse --short HEAD), universe $(basename "$U"), $(du -h "$OUT" | cut -f1)"

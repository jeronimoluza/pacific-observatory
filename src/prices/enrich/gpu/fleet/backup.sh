#!/usr/bin/env bash
# Copy a delta store to the 5TB and verify every bucket file by sha256.
#   ./backup.sh <store> <dest> <expected files, e.g. 768 = 3 tags x 256>
# Writes <dest>.sha256 next to the copy; exit 0 only when both lists are identical.
set -uo pipefail
S="${1:-}"; D="${2:-}"; N="${3:-}"
[ -d "$S" ] && [ -n "$D" ] && [ -n "$N" ] || { echo "usage: backup.sh <store> <dest> <expected files>" >&2; exit 1; }
findmnt -rno TARGET /mnt/backup5tb >/dev/null || { echo "BACKUP FAILED /mnt/backup5tb not mounted"; exit 1; }
mkdir -p "$D"
rsync -rt "$S/" "$D/" || { echo "BACKUP FAILED rsync $?"; exit 1; }
src=$(cd "$S" && find . -name '*.npz' | sort | xargs sha256sum)
dst=$(cd "$D" && find . -name '*.npz' | sort | xargs sha256sum)
n=$(printf '%s\n' "$src" | grep -c .)
printf '%s\n' "$dst" > "$D.sha256"
if [ "$n" = "$N" ] && [ "$src" = "$dst" ]; then
  echo "BACKUP DONE $n files sha equal $(date -u +%FT%TZ)"
else
  echo "BACKUP BAD files=$n expected=$N $(diff <(printf '%s\n' "$src") <(printf '%s\n' "$dst") | head -3)"; exit 1
fi

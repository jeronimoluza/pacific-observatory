#!/usr/bin/env bash
# Seed the panel36 run tree with the panel's weekly inputs, as REAL copies.
#
# Never hardlinks: score appends to _hierlex_pred and classify to decisions, so a
# hardlinked tree would write into production. Sources are only read.
# Per country (slugs in $PANEL_COUNTRIES): raw, concatenate shards, prepared,
# product months, classified + decisions parts. Global: _hierlex_pred (bucketed by
# name hash, not by country), the state files, the HierLex bundle, gold, the COICOP
# xlsx, _fx, weights, ppp and the official CPI csv the explorer reads.
#
# Refuses when a source is missing or holds a symlink, when the tree has a file
# newer than its source or not in the source (the tree has been run on), or when
# the copy would leave less than 20 GiB free. Re-running copies only what differs.
# Writes data/SEED_MANIFEST.tsv and checks count + bytes per group.
#
# Usage: scripts/mvp/seed_panel36.sh [--dry-run]
set -euo pipefail
shopt -s nullglob

DRY=0
case "${1:-}" in
  --dry-run) DRY=1 ;;
  "") ;;
  *) echo "usage: $0 [--dry-run]" >&2; exit 2 ;;
esac

TREE=${PANEL_TREE:-$HOME/po-worktrees/panel36}
COUNTRIES=${PANEL_COUNTRIES:-$HOME/scratch/embed_needs/panel36.txt}
PROD=$HOME/po/data/prices
ENRICH=$HOME/po/data_weekly/prices/enrich
SHARDS=$HOME/po/outputs/prices_refactor/raw
CPI=$HOME/po/data/cpi/official_cpi_monthly.csv
MIN_FREE=$((20 * 1024 * 1024 * 1024))
WORK=$(mktemp -d /tmp/seed_panel36.XXXXXX)
trap 'rm -rf "$WORK"' EXIT

[ -d "$TREE/.git" ] || [ -f "$TREE/.git" ] || { echo "not a worktree: $TREE" >&2; exit 1; }
if [ -L "$TREE/data" ]; then echo "$TREE/data is a symlink; it must be a real directory" >&2; exit 1; fi

missing=0
add() {
  if [ ! -e "$2" ]; then
    echo "MISSING $1 $2" >&2
    missing=$((missing + 1))
    return
  fi
  local src
  src=$(readlink -f "$2")
  [ -d "$src" ] && src="$src/"
  printf '%s\t%s\t%s\n' "$1" "$src" "$3" >> "$WORK/pairs.tsv"
}

while read -r c; do
  [ -n "$c" ] || continue
  dirs=("$PROD"/*/*/"$c")
  if [ ${#dirs[@]} -ne 1 ]; then
    echo "MISSING raw dir for $c (${#dirs[@]} matches)" >&2
    missing=$((missing + 1))
    continue
  fi
  key=${dirs[0]#"$PROD"/}
  add raw "$PROD/$key" "data/prices/$key/"
  add shards "$SHARDS/_per_source/$key" "outputs/prices/raw/_per_source/$key/"
  add prepared "$ENRICH/_prepared/$key.parquet" "data/prices/enrich/_prepared/$key.parquet"
  add months "$ENRICH/_prepared_months/$key.parquet" "data/prices/enrich/_prepared_months/$key.parquet"
  add classified "$ENRICH/cache/classified_hierlex/$c.parquet" "data/prices/enrich/cache/classified_hierlex/$c.parquet"
  add decisions "$ENRICH/cache/decisions_hierlex/$c.parquet" "data/prices/enrich/cache/decisions_hierlex/$c.parquet"
done < "$COUNTRIES"

add hierlex_pred "$ENRICH/_hierlex_pred" "data/prices/enrich/_hierlex_pred/"
add state "$ENRICH/_prepared/.state.json" "data/prices/enrich/_prepared/.state.json"
add state "$SHARDS/.state.json" "outputs/prices/raw/.state.json"
add state "$ENRICH/cache/decisions_hierlex/_decide.jsonl" "data/prices/enrich/cache/decisions_hierlex/_decide.jsonl"
add hierlex_bundle "$PROD/enrich/_models/hierlex" "data/prices/enrich/_models/hierlex/"
add reference "$PROD/enrich/gold" "data/prices/enrich/gold/"
add reference "$PROD/enrich/coicop_categories.xlsx" "data/prices/enrich/coicop_categories.xlsx"
add reference "$PROD/weights" "data/prices/weights/"
add reference "$PROD/ppp" "data/prices/ppp/"
add reference "$CPI" "data/cpi/official_cpi_monthly.csv"
add fx "$PROD/_fx" "data/prices/_fx/"

# One line per file: path relative to the pair root, size, mtime, ctime.
list() {
  if [ -d "$1" ]; then
    find "$1" -type f -printf '%P\t%s\t%T@\t%C@\n'
  elif [ -f "$1" ]; then
    find "$1" -maxdepth 0 -printf '%f\t%s\t%T@\t%C@\n'
  fi
}

# Plan: what each pair holds, what rsync would send, and what the tree has that it should not.
i=0
while IFS=$'\t' read -r g src dst; do
  i=$((i + 1))
  list "$src" > "$WORK/s$i"
  list "$TREE/$dst" > "$WORK/d$i"
  links=$(find "$src" -type l | wc -l)
  gawk -F'\t' -v g="$g" -v dst="$dst" -v links="$links" '
    FILENAME == ARGV[1] { ds[$1] = $2; dm[$1] = int($3); next }
    {
      n++; b += $2; seen[$1] = 1
      if (!($1 in ds) || ds[$1] != $2 || dm[$1] != int($3)) { tn++; tb += $2 }
      if (($1 in dm) && dm[$1] > int($3)) { newer++; if (newer <= 3) print "NEWER " dst $1 > "/dev/stderr" }
    }
    END {
      for (k in ds) if (!(k in seen)) { extra++; if (extra <= 3) print "EXTRA " dst k > "/dev/stderr" }
      printf "%s\t%d\t%d\t%d\t%d\t%d\t%d\t%d\n", g, n, b, tn, tb, newer, extra, links
    }' "$WORK/d$i" "$WORK/s$i" >> "$WORK/plan.tsv"
done < "$WORK/pairs.tsv"

avail=$(df -B1 --output=avail "$TREE" | tail -n 1 | tr -d ' ')
gawk -F'\t' -v avail="$avail" -v minfree="$MIN_FREE" -v missing="$missing" '
  function gib(x) { return sprintf("%.2f", x / 2^30) }
  { o[$1] = o[$1] ? o[$1] : ++k; name[o[$1]] = $1; p[$1]++
    n[$1] += $2; b[$1] += $3; tn[$1] += $4; tb[$1] += $5; nw[$1] += $6; ex[$1] += $7; ln[$1] += $8 }
  END {
    printf "%-15s %6s %9s %10s %10s %10s %6s %6s %6s\n", "group", "pairs", "files", "GiB", "copy_files", "copy_GiB", "newer", "extra", "links"
    for (j = 1; j <= k; j++) {
      g = name[j]
      printf "%-15s %6d %9d %10s %10d %10s %6d %6d %6d\n", g, p[g], n[g], gib(b[g]), tn[g], gib(tb[g]), nw[g], ex[g], ln[g]
      N += n[g]; B += b[g]; TN += tn[g]; TB += tb[g]; NW += nw[g]; EX += ex[g]; LN += ln[g]
    }
    printf "%-15s %6s %9d %10s %10d %10s %6d %6d %6d\n", "TOTAL", "", N, gib(B), TN, gib(TB), NW, EX, LN
    left = avail - TB
    printf "disk: %s GiB free now, %s GiB after copy, floor %s GiB\n", gib(avail), gib(left), gib(minfree)
    bad = 0
    if (missing > 0) { print "REFUSE: " missing " missing source(s)"; bad = 1 }
    if (NW + EX > 0) { print "REFUSE: tree has " NW " file(s) newer than source, " EX " not in source"; bad = 1 }
    if (LN > 0) { print "REFUSE: " LN " symlink(s) in sources"; bad = 1 }
    if (left < minfree) { print "REFUSE: copy would leave less than the free-space floor"; bad = 1 }
    exit bad
  }' "$WORK/plan.tsv" && ok=1 || ok=0

if [ "$DRY" = 1 ]; then
  echo "dry run: nothing copied (tree $TREE)"
  [ "$ok" = 1 ] && exit 0 || exit 1
fi
[ "$ok" = 1 ] || exit 1

started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "copy start $started"
while IFS=$'\t' read -r g src dst; do
  mkdir -p "$(dirname "$TREE/${dst%/}")"
  rsync -a "$src" "$TREE/$dst"
done < "$WORK/pairs.tsv"
echo "copy done $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Verify count + bytes per group; collect tree paths for the manifest.
i=0
: > "$WORK/verify.tsv"
: > "$WORK/src_all.tsv"
: > "$WORK/dst_all.tsv"
while IFS=$'\t' read -r g src dst; do
  i=$((i + 1))
  list "$src" > "$WORK/s$i"
  list "$TREE/$dst" > "$WORK/d$i"
  if [ -d "$src" ]; then pre=$dst; else pre=$(dirname "$dst")/; fi
  gawk -F'\t' -v OFS='\t' -v pre="$pre" '{ print pre $1, $2, $3 }' "$WORK/s$i" >> "$WORK/src_all.tsv"
  gawk -F'\t' -v OFS='\t' -v pre="$pre" '{ print pre $1, $2, $3, $4 }' "$WORK/d$i" >> "$WORK/dst_all.tsv"
  gawk -F'\t' -v g="$g" '
    FILENAME == ARGV[1] { ds[$1] = $2; next }
    { n++; b += $2; if ($1 in ds) { dn++; db += ds[$1] } }
    END { printf "%s\t%d\t%d\t%d\t%d\n", g, n, b, dn, db }' "$WORK/d$i" "$WORK/s$i" >> "$WORK/verify.tsv"
done < "$WORK/pairs.tsv"

gawk -F'\t' '
  { o[$1] = o[$1] ? o[$1] : ++k; name[o[$1]] = $1; n[$1] += $2; b[$1] += $3; dn[$1] += $4; db[$1] += $5 }
  END {
    printf "%-15s %9s %14s %9s %14s %s\n", "group", "src_files", "src_bytes", "dst_files", "dst_bytes", "result"
    for (j = 1; j <= k; j++) {
      g = name[j]; r = (n[g] == dn[g] && b[g] == db[g]) ? "OK" : "MISMATCH"; if (r != "OK") bad = 1
      printf "%-15s %9d %14d %9d %14d %s\n", g, n[g], b[g], dn[g], db[g], r
    }
    exit bad
  }' "$WORK/verify.tsv" && vbad=0 || vbad=1
echo "sha256 over $(wc -l < "$WORK/src_all.tsv") files"
(cd "$TREE" && cut -f1 "$WORK/src_all.tsv" | xargs -d '\n' sha256sum) > "$WORK/sha.txt" || true

manifest=$TREE/data/SEED_MANIFEST.tsv
gawk -F'\t' -v OFS='\t' '
  function utc(t) { return strftime("%Y-%m-%dT%H:%M:%SZ", int(t), 1) }
  FILENAME == ARGV[1] { line = $0; sha = substr(line, 1, 64); sub(/^[^ ]+  /, "", line); h[line] = sha; next }
  FILENAME == ARGV[2] { ct[$1] = $4; next }
  FNR == 1 { print "path", "bytes", "sha256", "src_mtime_utc", "copied_utc" }
  { print $1, $2, ($1 in h ? h[$1] : "NA"), utc($3), ($1 in ct ? utc(ct[$1]) : "NA") }
' "$WORK/sha.txt" "$WORK/dst_all.tsv" "$WORK/src_all.tsv" > "$manifest.tmp"
mv "$manifest.tmp" "$manifest"
echo "manifest $manifest: $(($(wc -l < "$manifest") - 1)) rows, $(grep -c $'\tNA' "$manifest" || true) with NA"

echo "seed done $(date -u +%Y-%m-%dT%H:%M:%SZ) (started $started)"
exit "$vbad"

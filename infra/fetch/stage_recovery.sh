#!/bin/bash
# Stage everything the recovery fleet downloads at boot, and prove it works
# before any instance exists.
#
#   bash stage_recovery.sh
#
# Safe to re-run and safe to run early: it uploads code and reads the bucket,
# and launches nothing. Costs are pennies of PUT requests. Run it whenever the
# parse tiers change; launch_recovery.sh refuses to start without it.
#
# The instances are keyless and unreachable, so anything wrong with the bundle
# is only visible hours later in a shipped log. That is why the bundle is
# imported and exercised here rather than trusted.
set -eu

BUCKET=pacific-observatory-cc-warc-934494149338
REGION=us-east-1
HERE=$(cd "$(dirname "$0")" && pwd)
VENV=/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo/.venv/bin/python
STAGE=${STAGE:-$(mktemp -d -t ccfetch-stage)}
export AWS_DEFAULT_REGION=$REGION

echo "== 1. credentials"
aws sts get-caller-identity --query 'Arn' --output text

echo
echo "== 2. build the parse bundle"
"$VENV" "$HERE/bundle_parse.py" "$STAGE/parse"
COUNT=$(find "$STAGE/parse" -name '*.py' | wc -l | tr -d ' ')
echo "modules staged: $COUNT"

echo
echo "== 3. import the bundle and run the full tier chain"
PARSE_DIR="$STAGE/parse" AWS_ACCESS_KEY_ID=x AWS_SECRET_ACCESS_KEY=y \
AWS_EC2_METADATA_DISABLED=true INPUT=misses \
"$VENV" - "$HERE" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import ccfetch
html = ('<html><body><script type="application/ld+json">'
        '{"@type":"Product","name":"probe","offers":'
        '{"@type":"Offer","price":"1.50","priceCurrency":"EUR"}}'
        '</script></body></html>')
rows, tier = ccfetch.parse_rows(html, "https://example.com/p/1", "livingcost")
# float, not string: normalize_price trims the trailing zero, so "1.50" comes
# back as "1.5" and a string compare fails on a chain that is working.
assert tier == "jsonld" and rows and float(rows[0]["price"]) == 1.5, (rows, tier)
print("   chain OK, tier=%s row=%r" % (tier, rows[0]["product_name"]))
print("   mode: INPUT=%s OUT=%s MISS_write=%s MISS_read=%s"
      % (ccfetch.INPUT, ccfetch.OUT_PREFIX, ccfetch.MISS_PREFIX,
         ccfetch.MISS_IN_PREFIX))
PY

echo
echo "== 4. upload"
aws s3 cp "$STAGE/parse.tar.gz" "s3://$BUCKET/fetch/parse.tar.gz"
aws s3 cp "$HERE/ccfetch.py"    "s3://$BUCKET/fetch/ccfetch.py"
aws s3 cp "$HERE/run.sh"        "s3://$BUCKET/fetch/run.sh"

echo
echo "== 5. confirm the recovery input is there"
CRAWLS=$(wc -l < "$HERE/crawls.txt" | tr -d ' ')
FIRST=$(head -1 "$HERE/crawls.txt")
N=$(aws s3 ls "s3://$BUCKET/misses/$FIRST/" | grep -c 'jsonl.gz' || true)
echo "crawls in list: $CRAWLS"
echo "miss objects under misses/$FIRST/: $N"
if [ "$N" -eq 0 ]; then
  echo "FAIL: no miss objects -- recovery has no input to read"
  exit 1
fi

echo
echo "staged. launch with:  bash $HERE/launch_recovery.sh 8"

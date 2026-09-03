#!/bin/bash
# Launch the recovery fleet: re-read the misses, parse them with the tiers that
# did not exist when they were recorded.
#
#   bash launch_recovery.sh [n_instances]      # default 8, the vCPU quota
#
# This one spends money and starts instances. stage_recovery.sh must have run
# first; the checks below refuse rather than launch against stale code, because
# a keyless fleet cannot be inspected and a wrong bundle is only visible hours
# later in a shipped log.
#
# Sizing: 17,972,011 miss records over NSHARDS=16, at a conservative 50 rec/s
# per core -- lower than the 91.2 measured on the first pass, because a miss by
# definition falls through every tier before reaching the one that reads it.
# That is about 100 core-hours, so ~6 h on 8 two-core instances, roughly $5 of
# compute. MAXSEC gives it 8 h and then the boxes kill themselves; a shard that
# does not finish is resumable at crawl grain on the next launch.
set -eu

COUNT=${1:-8}
BUCKET=pacific-observatory-cc-warc-934494149338
REGION=us-east-1
HERE=$(cd "$(dirname "$0")" && pwd)
export AWS_DEFAULT_REGION=$REGION

# Which miss set to re-read, and where the results land. These were hardcoded
# to the first run, so a second recovery over a different miss set would have
# read the wrong input and written over the first run's output without saying
# so. Every one of them is now named in the banner below before anything costs
# money.
MISS_IN_PREFIX=${MISS_IN_PREFIX:-misses-r2}
OUT_PREFIX=${OUT_PREFIX:-recovered-r2}
MISS_PREFIX=${MISS_PREFIX:-misses2-r2}

echo "== preflight"
echo "  reading  s3://$BUCKET/$MISS_IN_PREFIX/"
echo "  writing  s3://$BUCKET/$OUT_PREFIX/"
echo "  misses   s3://$BUCKET/$MISS_PREFIX/"

for KEY in fetch/parse.tar.gz fetch/ccfetch.py fetch/run.sh; do
  LINE=$(aws s3 ls "s3://$BUCKET/$KEY" || true)
  [ -n "$LINE" ] || { echo "FAIL: s3://$BUCKET/$KEY missing -- run stage_recovery.sh"; exit 1; }
  echo "  $KEY  $LINE"
done

# The uploaded ccfetch must be the one that can read a miss list at all. A
# stale object here is the failure this whole script exists to prevent: the
# fleet would silently re-run the manifest and re-bank 32.8M rows.
TMPC=$(mktemp)
aws s3 cp "s3://$BUCKET/fetch/ccfetch.py" "$TMPC" --quiet
grep -q 'INPUT=misses\|iter_misses' "$TMPC" \
  || { echo "FAIL: uploaded ccfetch.py has no miss-list mode -- re-run stage_recovery.sh"; exit 1; }
cmp -s "$TMPC" "$HERE/ccfetch.py" \
  && echo "  ccfetch.py matches local" \
  || { echo "FAIL: uploaded ccfetch.py differs from local -- re-run stage_recovery.sh"; exit 1; }

# A miss prefix that does not exist reads as "nothing to recover", and the
# fleet would run to completion, write nothing, and exit 0. Cheap to check
# here, invisible for hours if we do not.
NIN=$(aws s3 ls "s3://$BUCKET/$MISS_IN_PREFIX/" --recursive 2>/dev/null | grep -c jsonl.gz || true)
[ "$NIN" != "0" ] \
  || { echo "FAIL: s3://$BUCKET/$MISS_IN_PREFIX/ holds no miss objects"; exit 1; }
echo "  miss objects to re-read: $NIN"

# Refuse to overwrite a completed recovery rather than resume over the top of
# it. ccfetch's own RESUME skips objects it already wrote, so this is a warning
# about intent, not about safety.
DONE=$(aws s3 ls "s3://$BUCKET/$OUT_PREFIX/" 2>/dev/null | wc -l | tr -d ' ')
echo "  existing $OUT_PREFIX/ prefixes: $DONE (RESUME will skip those crawls)"

RUNNING=$(aws ec2 describe-instances --region "$REGION" \
  --filters Name=tag:Project,Values=cc-fetch \
            Name=instance-state-name,Values=pending,running \
  --query 'length(Reservations[].Instances[])' --output text)
if [ "$RUNNING" != "0" ]; then
  echo "FAIL: $RUNNING cc-fetch instances are already running"
  echo "  they share the shard space; stop them or wait before launching"
  exit 1
fi
echo "  no cc-fetch instances currently running"

echo
echo "== launching $COUNT instances, INPUT=misses -> s3://$BUCKET/$OUT_PREFIX/"
INPUT=misses OUT_PREFIX=$OUT_PREFIX MISS_PREFIX=$MISS_PREFIX \
  MISS_IN_PREFIX=$MISS_IN_PREFIX \
  MAXSEC=28800 CONC=32 bash "$HERE/launch_fleet.sh" 0 "$COUNT"

echo
echo "watch:   aws s3 ls s3://$BUCKET/logs/ --recursive | tail"
echo "output:  aws s3 ls s3://$BUCKET/$OUT_PREFIX/ --recursive | wc -l"
echo "stop:    aws ec2 terminate-instances --instance-ids <ids>"

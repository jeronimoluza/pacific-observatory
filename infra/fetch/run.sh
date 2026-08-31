#!/bin/bash
# Bootstrap one fetch instance: pull the parser, run N shards, ship logs.
#
# The instances carry no SSH key and no SSM agent, so the only way to see what
# a run is doing is to push it out. Logs go to s3://$BUCKET/logs/<instance-id>/
# every 60s, which also means a self-terminating box leaves its evidence behind.
#
# Set by UserData: CRAWLS, NSHARDS, SHARD_BASE, NPROC, CONC, OUT_PREFIX,
#                  MAXSEC, TERMINATE, INPUT
exec > /var/log/ccfetch-boot.log 2>&1
set -x

# Exported, not passed on the per-process command line, and only when actually
# set. ccfetch resolves OUT_PREFIX/MISS_PREFIX from INPUT when they are absent,
# but `OUT_PREFIX=` in the environment is present-and-empty: os.environ.get
# returns "" rather than the default, and the run writes to the bucket root.
export INPUT=${INPUT:-manifest}
[ -n "${OUT_PREFIX:-}" ] && export OUT_PREFIX || unset OUT_PREFIX
[ -n "${MISS_PREFIX:-}" ] && export MISS_PREFIX || unset MISS_PREFIX
[ -n "${MISS_IN_PREFIX:-}" ] && export MISS_IN_PREFIX || unset MISS_IN_PREFIX

BUCKET=pacific-observatory-cc-warc-934494149338
export AWS_DEFAULT_REGION=us-east-1

TOK=$(curl -sX PUT http://169.254.169.254/latest/api/token \
      -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
IID=$(curl -s -H "X-aws-ec2-metadata-token: $TOK" \
      http://169.254.169.254/latest/meta-data/instance-id)
echo "instance=$IID crawls=$CRAWLS shards=$SHARD_BASE+$NPROC of $NSHARDS"

dnf install -y python3-pip
pip3 install --quiet boto3 lxml

mkdir -p /opt/cc/parse
aws s3 cp "s3://$BUCKET/fetch/parse.tar.gz" /opt/cc/parse.tar.gz
aws s3 cp "s3://$BUCKET/fetch/ccfetch.py"  /opt/cc/ccfetch.py
tar xzf /opt/cc/parse.tar.gz -C /opt/cc/parse
ls -la /opt/cc/parse

ship_logs() {
  aws s3 cp /var/log/ccfetch-boot.log "s3://$BUCKET/logs/$IID/boot.log" --quiet
  for f in /var/log/ccfetch-shard-*.log; do
    [ -e "$f" ] || continue
    aws s3 cp "$f" "s3://$BUCKET/logs/$IID/$(basename "$f")" --quiet
  done
}
( while true; do ship_logs; sleep 60; done ) &

# Hard stop. A wedged process on a keyless instance cannot be fixed by hand,
# so the box kills itself rather than billing until someone notices.
( sleep "${MAXSEC:-21600}"
  echo "MAXSEC reached, terminating"
  ship_logs
  T=$(curl -sX PUT http://169.254.169.254/latest/api/token \
      -H "X-aws-ec2-metadata-token-ttl-seconds: 300")
  I=$(curl -s -H "X-aws-ec2-metadata-token: $T" \
      http://169.254.169.254/latest/meta-data/instance-id)
  aws ec2 terminate-instances --instance-ids "$I" ) &

export PARSE_DIR=/opt/cc/parse
export OUT_BUCKET=$BUCKET
export MANIFEST_BUCKET=$BUCKET

# One process per core: the parse tiers are pure Python and hold the GIL, so
# CONC only ever parallelises the S3 fetch, never the parse.
PIDS=""
for i in $(seq 0 $((NPROC - 1))); do
  S=$((SHARD_BASE + i))
  SHARD=$S NSHARDS=$NSHARDS CONC=$CONC CRAWLS=$CRAWLS \
    nohup python3 /opt/cc/ccfetch.py > "/var/log/ccfetch-shard-$S.log" 2>&1 &
  PIDS="$PIDS $!"
done
for p in $PIDS; do wait "$p"; done

echo "all shards finished"
ship_logs
if [ "${TERMINATE:-1}" = "1" ]; then
  T=$(curl -sX PUT http://169.254.169.254/latest/api/token \
      -H "X-aws-ec2-metadata-token-ttl-seconds: 300")
  I=$(curl -s -H "X-aws-ec2-metadata-token: $T" \
      http://169.254.169.254/latest/meta-data/instance-id)
  aws ec2 terminate-instances --instance-ids "$I"
fi

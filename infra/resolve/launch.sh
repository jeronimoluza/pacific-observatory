#!/bin/bash
# Launch one cdx resolve instance.
#
# The August run was launched by hand, which is why there was nothing to re-read
# when it came time to do a second one. This is that command, written down.
#
# DST_PREFIX is the parameter that matters. ccresolve keys its output by crawl,
# so a run over a different source set pointed at the same prefix overwrites the
# previous run's manifests rather than adding to them. Every run gets its own.
set -eu

BUCKET=pacific-observatory-cc-warc-934494149338
REGION=us-east-1
AMI=ami-0332d564d76dbd8d6
TYPE=${TYPE:-c7i-flex.large}
PROFILE=cc-fetch-ec2-profile

RUN_TAG=${RUN_TAG:?set RUN_TAG, e.g. r2}
SHARD=${SHARD:-0}
SRC_KEY=${SRC_KEY:?set SRC_KEY, e.g. resolve/sources-r2.json}
DST_PREFIX=${DST_PREFIX:?set DST_PREFIX, e.g. resolve/manifests-r2}
CONC=${CONC:-32}

UD=$(mktemp)
cat > "$UD" <<EOF
#!/bin/bash
export RUN_TAG=$RUN_TAG
export SHARD=$SHARD
export SRC_KEY=$SRC_KEY
export DST_PREFIX=$DST_PREFIX
export CONC=$CONC
aws s3 cp s3://$BUCKET/resolve/boot.sh /tmp/boot.sh
bash /tmp/boot.sh
EOF

aws ec2 run-instances \
  --region "$REGION" \
  --image-id "$AMI" \
  --instance-type "$TYPE" \
  --iam-instance-profile "Name=$PROFILE" \
  --instance-initiated-shutdown-behavior terminate \
  --user-data "file://$UD" \
  --tag-specifications \
    "ResourceType=instance,Tags=[{Key=Name,Value=ccresolve-$RUN_TAG-$SHARD},{Key=job,Value=ccresolve}]" \
  --query 'Instances[0].InstanceId' --output text

rm -f "$UD"

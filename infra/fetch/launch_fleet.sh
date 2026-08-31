#!/bin/bash
# Launch fetch instances for a range of shards.
#
#   bash launch_fleet.sh <first_shard_base> <n_instances>
#
# Each instance runs 2 processes (one per vCPU, since the parse holds the GIL),
# so instance k covers shards base+2k and base+2k+1 of NSHARDS.
#
# Deliberately ramped rather than launched all at once: 64 concurrent reads from
# one instance is verified, the fleet-wide rate is not, and a Common Crawl block
# discovered at hour three costs a lot more than a ten minute check.
#
# INPUT selects the workload and is passed through to ccfetch: `manifest` (the
# default) reads the resolved captures, `misses` re-reads only what failed to
# parse. Callers normally reach the recovery mode through launch_recovery.sh
# rather than setting it here.
set -eu

BASE=${1:?first shard base}
COUNT=${2:?number of instances}

BUCKET=pacific-observatory-cc-warc-934494149338
REGION=us-east-1
AMI=ami-0332d564d76dbd8d6
TYPE=c7i-flex.large
PROFILE=cc-fetch-ec2-profile
NSHARDS=16
INPUT=${INPUT:-manifest}
MAXSEC=${MAXSEC:-54000}
CONC=${CONC:-32}
# In the repo, not the job scratch dir: the scratch dir is deleted with the
# session, and a launch that silently loses its crawl list is worse than one
# that fails to start.
HERE=$(cd "$(dirname "$0")" && pwd)
CRAWLS=$(paste -sd, "$HERE/crawls.txt")
# Kept after the run rather than cleaned up: the instances are keyless, so the
# generated UserData is the only record of what a box was actually told to do.
UDDIR=${UDDIR:-$(mktemp -d -t ccfetch-userdata)}

# Spread across AZs: eight of one instance type in a single AZ is a capacity
# refusal waiting to happen.
SUBNETS=(subnet-06c566e8433daac1e subnet-03f82ddd7c8195957 \
         subnet-08b238cd8cc39b64d subnet-00ad01af4a1653d15)

i=0
while [ "$i" -lt "$COUNT" ]; do
  SB=$((BASE + i * 2))
  SUB=${SUBNETS[$((i % ${#SUBNETS[@]}))]}
  UD=$UDDIR/userdata-shard-$SB.sh
  # OUT_PREFIX and MISS_PREFIX are deliberately NOT written when the caller has
  # not set them: ccfetch derives both from INPUT, and an empty assignment here
  # would override that derivation with the empty string.
  {
    echo "#!/bin/bash"
    echo "export CRAWLS=$CRAWLS"
    echo "export NSHARDS=$NSHARDS"
    echo "export SHARD_BASE=$SB"
    echo "export NPROC=2"
    echo "export CONC=$CONC"
    echo "export INPUT=$INPUT"
    [ -n "${OUT_PREFIX:-}" ] && echo "export OUT_PREFIX=$OUT_PREFIX"
    [ -n "${MISS_PREFIX:-}" ] && echo "export MISS_PREFIX=$MISS_PREFIX"
    [ -n "${MISS_IN_PREFIX:-}" ] && echo "export MISS_IN_PREFIX=$MISS_IN_PREFIX"
    echo "export MAXSEC=$MAXSEC"
    echo "export TERMINATE=1"
    echo "export AWS_DEFAULT_REGION=$REGION"
    echo "aws s3 cp s3://$BUCKET/fetch/run.sh /opt/run.sh"
    echo "bash /opt/run.sh"
  } > "$UD"

  ID=$(aws ec2 run-instances --region "$REGION" \
    --image-id "$AMI" --instance-type "$TYPE" --subnet-id "$SUB" \
    --iam-instance-profile Name=$PROFILE \
    --user-data "file://$UD" \
    --block-device-mappings \
      '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":20,"VolumeType":"gp3","DeleteOnTermination":true}}]' \
    --tag-specifications \
      "ResourceType=instance,Tags=[{Key=Project,Value=cc-fetch},{Key=Name,Value=cc-shard-$SB}]" \
    --instance-initiated-shutdown-behavior terminate \
    --query 'Instances[0].InstanceId' --output text)
  echo "shard $SB,$((SB + 1))  $ID  $SUB"
  i=$((i + 1))
done

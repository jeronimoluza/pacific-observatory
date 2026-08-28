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
set -eu

BASE=${1:?first shard base}
COUNT=${2:?number of instances}

BUCKET=pacific-observatory-cc-warc-934494149338
REGION=us-east-1
AMI=ami-0332d564d76dbd8d6
TYPE=c7i-flex.large
PROFILE=cc-fetch-ec2-profile
NSHARDS=16
TMP=/Users/jeronimoluza/.claude/jobs/f8501cf5/tmp
CRAWLS=$(paste -sd, "$TMP/crawls.txt")

# Spread across AZs: eight of one instance type in a single AZ is a capacity
# refusal waiting to happen.
SUBNETS=(subnet-06c566e8433daac1e subnet-03f82ddd7c8195957 \
         subnet-08b238cd8cc39b64d subnet-00ad01af4a1653d15)

i=0
while [ "$i" -lt "$COUNT" ]; do
  SB=$((BASE + i * 2))
  SUB=${SUBNETS[$((i % ${#SUBNETS[@]}))]}
  UD=$TMP/userdata-shard-$SB.sh
  cat > "$UD" <<EOF
#!/bin/bash
export CRAWLS=$CRAWLS
export NSHARDS=$NSHARDS
export SHARD_BASE=$SB
export NPROC=2
export CONC=32
export OUT_PREFIX=parsed
export MAXSEC=54000
export TERMINATE=1
export AWS_DEFAULT_REGION=$REGION
aws s3 cp s3://$BUCKET/fetch/run.sh /opt/run.sh
bash /opt/run.sh
EOF

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

#!/bin/bash
# Bootstrap for the cdx resolve job.
#
# Lives on S3 rather than in UserData: the aws-mcp proxy parses UserData for
# CLI flags, so any dash-prefixed token inside the script (-x, -C, --quiet) is
# misread as an argument to run-instances and the launch is rejected. UserData
# stays a two-line stub that copies this down and runs it.
#
# Everything is teed to a log shipped to S3 on the way out, including on
# failure: GetConsoleOutput returns empty for the whole life of a short-lived
# instance, so it is not a usable channel for finding out why a run produced
# nothing.
set -x
exec > /tmp/boot.log 2>&1

BUCKET=pacific-observatory-cc-warc-934494149338
RUN=${RUN_TAG:-resolve}
SHARD=${SHARD:-0}

ship() {
  aws s3 cp /tmp/boot.log s3://$BUCKET/resolve/$RUN-$SHARD-boot.log
}
trap ship EXIT

# Backstop only. The job self-terminates below; this catches a hang.
shutdown -h +240

dnf install -y python3-pip
pip3 install --quiet boto3

aws s3 cp s3://$BUCKET/resolve/ccresolve.py /tmp/ccresolve.py
aws s3 cp s3://$BUCKET/resolve/sources.json /tmp/sources.json
aws s3 cp s3://$BUCKET/resolve/crawls-$SHARD.txt /tmp/crawls.txt

nproc
python3 --version
wc -l /tmp/crawls.txt

export SOURCES=/tmp/sources.json
export OUT_BUCKET=$BUCKET
export OUT_PREFIX=resolve/manifests
export CONC=${CONC:-64}
export CRAWLS=$(tr '\n' ',' < /tmp/crawls.txt)

python3 /tmp/ccresolve.py
echo "resolve exit: $?"

ship
shutdown -h now

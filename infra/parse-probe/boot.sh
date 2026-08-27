#!/bin/bash
# Bootstrap for the parse-yield probe.
#
# Lives on S3 rather than in UserData: the aws-mcp proxy parses UserData for
# CLI flags, so any dash-prefixed token inside the script (-x, -C, --quiet)
# is misread as an argument to run-instances and the launch is rejected.
#
# Everything is teed to a log that is shipped to S3 on the way out, including
# on failure. GetConsoleOutput returns empty for the whole life of a
# short-lived instance, so it is not a usable channel for finding out why a
# run produced nothing.
set -x
exec > /tmp/boot.log 2>&1

BUCKET=pacific-observatory-cc-warc-934494149338
RUN=${RUN_TAG:-run2}

ship() {
  aws s3 cp /tmp/boot.log s3://$BUCKET/parse-probe/$RUN-boot.log
}
trap ship EXIT

shutdown -h +90                      # backstop; generous, the probe self-terminates

dnf install -y python3-pip gcc python3-devel
pip3 install --quiet boto3 beautifulsoup4 lxml

mkdir -p /tmp/parse
aws s3 cp s3://$BUCKET/parse-probe/parse.tar.gz /tmp/parse.tar.gz
tar xzf /tmp/parse.tar.gz -C /tmp/parse
aws s3 cp s3://$BUCKET/parse-probe/probe_sample.jsonl.gz /tmp/probe_sample.jsonl.gz
aws s3 cp s3://$BUCKET/parse-probe/probe.py /tmp/probe.py

nproc
python3 --version

export OUT_BUCKET=$BUCKET
export RESULT_KEY=parse-probe/$RUN-result.json
export N_PROC=2
export N_THREAD=32
python3 /tmp/probe.py
echo "probe exit: $?"

ship

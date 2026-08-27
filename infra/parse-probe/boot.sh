#!/bin/bash
# Bootstrap for the parse-yield probe.
#
# Lives on S3 rather than in UserData: the aws-mcp proxy parses UserData for
# CLI flags, so any dash-prefixed token inside the script (-x, -C, --quiet)
# is misread as an argument to run-instances and the launch is rejected.
set -x
BUCKET=pacific-observatory-cc-warc-934494149338

shutdown -h +40                      # backstop if the probe wedges

dnf install -y python3-pip gcc python3-devel
pip3 install --quiet boto3 beautifulsoup4 lxml

mkdir -p /tmp/parse
aws s3 cp s3://$BUCKET/parse-probe/parse.tar.gz /tmp/parse.tar.gz
tar xzf /tmp/parse.tar.gz -C /tmp/parse
aws s3 cp s3://$BUCKET/parse-probe/probe_sample.jsonl.gz /tmp/probe_sample.jsonl.gz
aws s3 cp s3://$BUCKET/parse-probe/probe.py /tmp/probe.py

export OUT_BUCKET=$BUCKET
export N_PROC=2
export N_THREAD=32
python3 /tmp/probe.py

# Probe self-terminates on success. If it died, fall back to the shutdown
# backstop above rather than leaving the instance billing.

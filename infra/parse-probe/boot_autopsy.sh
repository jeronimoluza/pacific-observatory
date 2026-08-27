#!/bin/bash
# Bootstrap for the miss autopsy.
#
# Same shape as boot.sh: lives on S3 because the aws-mcp proxy parses UserData
# for CLI flags, so a dash-prefixed token inside the script is misread as an
# argument to run-instances. Everything is teed to a log shipped to S3 on the
# way out, including on failure, because GetConsoleOutput stays empty for the
# whole life of a short-lived instance.
set -x
exec > /tmp/boot.log 2>&1

BUCKET=pacific-observatory-cc-warc-934494149338
RUN=${RUN_TAG:-autopsy1}

ship() {
  aws s3 cp /tmp/boot.log s3://$BUCKET/parse-probe/$RUN-boot.log
}
trap ship EXIT

shutdown -h +90                      # backstop; the autopsy self-terminates

dnf install -y python3-pip gcc python3-devel
pip3 install --quiet boto3 beautifulsoup4 lxml

mkdir -p /tmp/parse
aws s3 cp s3://$BUCKET/parse-probe/parse.tar.gz /tmp/parse.tar.gz
tar xzf /tmp/parse.tar.gz -C /tmp/parse
aws s3 cp s3://$BUCKET/parse-probe/probe_sample.jsonl.gz /tmp/probe_sample.jsonl.gz
aws s3 cp s3://$BUCKET/parse-probe/autopsy.py /tmp/autopsy.py

nproc
df -h /tmp
python3 --version

export OUT_BUCKET=$BUCKET
export RESULT_KEY=parse-probe/$RUN-result.json
export MISS_PREFIX=parse-probe/miss-html/
export N_PROC=2
export N_THREAD=32
python3 /tmp/autopsy.py
echo "autopsy exit: $?"

ship

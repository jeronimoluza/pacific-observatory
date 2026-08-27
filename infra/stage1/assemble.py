TMP = "/Users/jeronimoluza/.claude/jobs/f8501cf5/tmp"
OUT_BUCKET = "pacific-observatory-cc-warc-934494149338"

payload = open(TMP + "/slice.b64").read().strip()
probe = open(TMP + "/probe.py").read()
probe = probe.replace("@@PAYLOAD@@", payload).replace("@@OUT_BUCKET@@", OUT_BUCKET)

with open(TMP + "/probe_final.py", "w") as f:
    f.write(probe)

userdata = (
    "#!/bin/bash\n"
    "exec > >(tee /dev/console) 2>&1\n"
    "set -x\n"
    "shutdown -h +25\n"
    "dnf install -y python3-pip\n"
    "pip3 install --quiet boto3\n"
    "aws s3 cp s3://%s/stage1/probe.py /tmp/probe.py\n"
    "python3 /tmp/probe.py\n"
) % OUT_BUCKET

with open(TMP + "/userdata.sh", "w") as f:
    f.write(userdata)

print("probe_final.py bytes:", len(probe.encode()))
print("userdata bytes:", len(userdata.encode()), "(limit 16384)")
print("--- userdata ---")
print(userdata)

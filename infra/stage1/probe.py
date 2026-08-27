import base64, gzip, json, os, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

import boto3
from botocore.config import Config

PAYLOAD = "@@PAYLOAD@@"
OUT_BUCKET = "@@OUT_BUCKET@@"
SRC_BUCKET = "commoncrawl"

d = json.loads(gzip.decompress(base64.b64decode(PAYLOAD)))
crawl, segs, recs = d["c"], d["s"], d["r"]


def key_of(r):
    seg, s, e = segs[r[0]].split("|")
    return "crawl-data/%s/segments/%s/warc/CC-MAIN-%s-%s-%05d.warc.gz" % (
        crawl, seg, s, e, r[1],
    )


cfg = Config(
    max_pool_connections=160,
    retries={"max_attempts": 3, "mode": "standard"},
    connect_timeout=15,
    read_timeout=60,
)
s3 = boto3.client("s3", config=cfg)

result = {"crawl": crawl, "n_records": len(recs), "runs": [], "errors": []}


def fetch(r):
    t0 = time.time()
    try:
        body = s3.get_object(
            Bucket=SRC_BUCKET,
            Key=key_of(r),
            Range="bytes=%d-%d" % (r[2], r[2] + r[3] - 1),
        )["Body"].read()
        return (True, len(body), time.time() - t0, body)
    except Exception as ex:
        return (False, 0, time.time() - t0, "%s: %s" % (type(ex).__name__, ex))


# --- A. does an unauthenticated-payer GET work at all? ---
probe_ok, _, probe_dt, probe_info = fetch(recs[0])
result["single_get_ok"] = probe_ok
result["single_get_seconds"] = round(probe_dt, 4)
if not probe_ok:
    result["single_get_error"] = probe_info
    print("FATAL first GET failed:", probe_info)

# --- B. throughput at increasing concurrency ---
groups = [(1, 40), (8, 120), (32, 300), (64, 540)]
pos = 0
for conc, n in groups:
    batch = recs[pos:pos + n]
    pos += n
    if not batch:
        continue
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=conc) as ex:
        out = list(ex.map(fetch, batch))
    wall = time.time() - t0
    ok = [o for o in out if o[0]]
    bad = [o for o in out if not o[0]]
    lat = sorted(o[2] for o in ok)
    byts = sum(o[1] for o in ok)
    run = {
        "concurrency": conc,
        "requested": len(batch),
        "bytes": byts,
        "ok": len(ok),
        "failed": len(bad),
        "wall_seconds": round(wall, 3),
        "records_per_sec": round(len(ok) / wall, 2) if wall else None,
        "MB_per_sec": round(byts / 1e6 / wall, 2) if wall else None,
        "median_latency_ms": round(lat[len(lat) // 2] * 1000, 1) if lat else None,
        "p95_latency_ms": round(lat[int(len(lat) * 0.95)] * 1000, 1) if lat else None,
    }
    result["runs"].append(run)
    for b in bad[:3]:
        result["errors"].append({"concurrency": conc, "error": b[3]})
    print("conc=%-3d ok=%-4d fail=%-3d %6.1f rec/s %6.1f MB/s p50=%sms" % (
        conc, len(ok), len(bad), run["records_per_sec"] or 0,
        run["MB_per_sec"] or 0, run["median_latency_ms"]))

# --- C. is the payload real, parseable WARC/HTML? ---
parsed = {"tried": 0, "gunzip_ok": 0, "html_ok": 0}
for r in recs[:12]:
    ok, _, _, body = fetch(r)
    if not ok:
        continue
    parsed["tried"] += 1
    try:
        raw = gzip.decompress(body)
    except Exception:
        continue
    parsed["gunzip_ok"] += 1
    i = raw.find(b"\r\n\r\n")
    j = raw.find(b"\r\n\r\n", i + 4) if i >= 0 else -1
    if j > 0 and b"<" in raw[j + 4:j + 4000]:
        parsed["html_ok"] += 1
result["parse_check"] = parsed
print("parse check:", parsed)

# --- D. can the index (cdx) layer be read from the same bucket? ---
try:
    h = s3.head_object(
        Bucket=SRC_BUCKET,
        Key="cc-index/collections/%s/indexes/cluster.idx" % crawl,
    )
    result["cluster_idx_bytes"] = h["ContentLength"]
    blk = s3.get_object(
        Bucket=SRC_BUCKET,
        Key="cc-index/collections/%s/indexes/cdx-00000.gz" % crawl,
        Range="bytes=0-262143",
    )["Body"].read()
    result["cdx_block_ok"] = len(blk) > 0
    result["cdx_block_bytes"] = len(blk)
except Exception as ex:
    result["cdx_error"] = "%s: %s" % (type(ex).__name__, ex)
print("index layer:", result.get("cluster_idx_bytes"), result.get("cdx_error", "ok"))

# --- E. instance identity + cost context ---
try:
    tok = urllib.request.urlopen(urllib.request.Request(
        "http://169.254.169.254/latest/api/token", method="PUT",
        headers={"X-aws-ec2-metadata-token-ttl-seconds": "300"}), timeout=5).read().decode()
    def imds(p):
        return urllib.request.urlopen(urllib.request.Request(
            "http://169.254.169.254/latest/meta-data/" + p,
            headers={"X-aws-ec2-metadata-token": tok}), timeout=5).read().decode()
    iid = imds("instance-id")
    result["instance_id"] = iid
    result["instance_type"] = imds("instance-type")
    result["az"] = imds("placement/availability-zone")
except Exception as ex:
    iid = None
    result["imds_error"] = str(ex)

result["total_bytes_fetched"] = sum(r["bytes"] for r in result["runs"])
result["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

blob = json.dumps(result, indent=2)
print("=== STAGE1 RESULT JSON ===")
print(blob)
print("=== END STAGE1 RESULT ===")

try:
    boto3.client("s3").put_object(
        Bucket=OUT_BUCKET, Key="stage1/probe-result.json",
        Body=blob.encode(), ContentType="application/json")
    print("wrote s3://%s/stage1/probe-result.json" % OUT_BUCKET)
except Exception as ex:
    print("could not write result to S3:", ex)

if iid:
    try:
        boto3.client("ec2").terminate_instances(InstanceIds=[iid])
        print("self-terminate requested")
    except Exception as ex:
        print("self-terminate failed:", ex)
        os.system("shutdown -h now")

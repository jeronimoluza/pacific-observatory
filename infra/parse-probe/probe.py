"""Parse-yield probe: how much of the archive can we actually read, by year.

Answers the question archive depth does not: a capture existing in Common Crawl
says nothing about whether our extraction can read a price out of it. Selectors
are written against current markup, so yield by capture year is the real limit
on how far back a price series can go.

Measures the ladder twice per page - selectors-only (the pre-fix behaviour) and
the full fall-through - so the value of the fall-through fix is a direct
subtraction rather than a comparison across two runs.

Excludes spider `parse_html` hooks: they need scrapy and per-spider config, and
they cover 0.4% of records and none of the top 20 sources. Reported as such.
"""
import collections
import gzip
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pool

import boto3
from botocore.config import Config

sys.path.insert(0, "/tmp/parse")

from archived import row_from_meta, rows_from_jsonld            # noqa: E402
from archived_embedded import rows_from_next_flight             # noqa: E402
from selectors_mod import extract_with_fallback, get_selectors  # noqa: E402
from bs4 import BeautifulSoup                                   # noqa: E402

SRC_BUCKET = "commoncrawl"
OUT_BUCKET = os.environ.get("OUT_BUCKET", "@@OUT_BUCKET@@")
SAMPLE = "/tmp/probe_sample.jsonl.gz"
RESULT_KEY = os.environ.get("RESULT_KEY", "parse-probe/result.json")
N_PROC = int(os.environ.get("N_PROC", "16"))
N_THREAD = int(os.environ.get("N_THREAD", "8"))

_S3 = None


def s3():
    global _S3
    if _S3 is None:
        _S3 = boto3.client("s3", config=Config(
            max_pool_connections=N_THREAD * 4,
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=15, read_timeout=60))
    return _S3


# ---------- fetch ----------

def fetch(rec):
    try:
        body = s3().get_object(
            Bucket=SRC_BUCKET, Key=rec["f"],
            Range="bytes=%d-%d" % (rec["o"], rec["o"] + rec["l"] - 1),
        )["Body"].read()
        return body
    except Exception:
        return None


def html_of(raw):
    """Strip the WARC envelope then the HTTP headers; decode leniently."""
    try:
        blob = gzip.decompress(raw)
    except Exception:
        return None, "gunzip_failed"
    i = blob.find(b"\r\n\r\n")
    if i < 0:
        return None, "no_warc_envelope"
    j = blob.find(b"\r\n\r\n", i + 4)
    if j < 0:
        return None, "no_http_headers"
    body = blob[j + 4:]
    if not body.strip():
        return None, "empty_body"
    for enc in ("utf-8", "latin-1"):
        try:
            return body.decode(enc), None
        except UnicodeDecodeError:
            continue
    return body.decode("utf-8", "replace"), None


# ---------- the ladder, both ways ----------

def selector_row(html, selectors):
    """Pre-fix behaviour: selectors only, any non-empty dict counts."""
    if not selectors:
        return None
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    for field, sel_list in selectors.items():
        v = extract_with_fallback(soup, sel_list)
        if v:
            out[field] = v
    return out or None


def generic_rows(html, url):
    rows = rows_from_jsonld(html, url)
    if rows:
        return rows, "jsonld"
    row = row_from_meta(html, url)
    if row:
        return [row], "meta"
    rows = rows_from_next_flight(html, url)
    if rows:
        return rows, "next_flight"
    return [], None


def parse_both(html, url, selectors):
    """Return (old_hit, new_hit, tier, n_rows). old = selectors-only w/ any field."""
    sr = selector_row(html, selectors)
    old_hit = bool(sr)
    if sr and sr.get("price"):
        return old_hit, True, "selectors", 1
    rows, tier = generic_rows(html, url)
    if rows:
        return old_hit, True, tier, len(rows)
    if sr:
        # partial selector row, no price anywhere - not a usable observation
        return old_hit, False, "selectors_noprice", 1
    return old_hit, False, None, 0


# ---------- per-record work ----------

SELCACHE = {}


def selectors_for(spider):
    if spider not in SELCACHE:
        try:
            SELCACHE[spider] = get_selectors(spider)
        except Exception:
            SELCACHE[spider] = {}
    return SELCACHE[spider]


def one(rec):
    t0 = time.time()
    raw = fetch(rec)
    t_fetch = time.time() - t0
    base = {"s": rec["s"], "c": rec["c"], "g": rec["g"], "t_fetch": t_fetch}
    if raw is None:
        return dict(base, status="fetch_failed", t_parse=0.0)
    html, err = html_of(raw)
    if html is None:
        return dict(base, status=err, t_parse=0.0, bytes=len(raw))
    t1 = time.time()
    try:
        old_hit, new_hit, tier, n = parse_both(html, rec["u"], selectors_for(rec["s"]))
    except Exception as ex:
        return dict(base, status="parse_error", t_parse=time.time() - t1,
                    err=str(ex)[:120], bytes=len(raw))
    t_parse = time.time() - t1
    return dict(base, status="ok", t_parse=t_parse, bytes=len(raw),
                html_kb=len(html) / 1024.0, tags=html.count("<"),
                old_hit=old_hit, new_hit=new_hit, tier=tier, n_rows=n)


def chunk(recs):
    with ThreadPoolExecutor(max_workers=N_THREAD) as ex:
        return list(ex.map(one, recs))


# ---------- driver ----------

def main():
    recs = [json.loads(l) for l in gzip.open(SAMPLE, "rt")]
    print("records: %d  procs: %d  threads/proc: %d" % (len(recs), N_PROC, N_THREAD))
    chunks = [recs[i::N_PROC * 4] for i in range(N_PROC * 4)]

    t0 = time.time()
    out = []
    with Pool(N_PROC) as pool:
        for i, part in enumerate(pool.imap_unordered(chunk, chunks), 1):
            out.extend(part)
            if i % 8 == 0:
                el = time.time() - t0
                print("  %d/%d chunks  %d recs  %.0f rec/s" % (
                    i, len(chunks), len(out), len(out) / el), flush=True)
    wall = time.time() - t0

    # ---- aggregate ----
    cell = collections.defaultdict(lambda: collections.Counter())
    for r in out:
        k = (r["c"], r["g"])
        c = cell[k]
        c["n"] += 1
        c[r["status"]] += 1
        if r["status"] == "ok":
            c["old_hit"] += int(r["old_hit"])
            c["new_hit"] += int(r["new_hit"])
            c["tier_" + str(r["tier"])] += 1

    by_source = collections.defaultdict(lambda: collections.Counter())
    for r in out:
        c = by_source[(r["s"], r["c"])]
        c["n"] += 1
        if r["status"] == "ok":
            c["old_hit"] += int(r["old_hit"])
            c["new_hit"] += int(r["new_hit"])

    ok = [r for r in out if r["status"] == "ok"]
    tp = sorted(r["t_parse"] for r in ok)
    tags = sorted(r["tags"] for r in ok)

    def pct(a, p):
        return a[int(len(a) * p)] if a else None

    result = {
        "n_records": len(out),
        "wall_seconds": round(wall, 1),
        "records_per_sec": round(len(out) / wall, 1),
        "n_proc": N_PROC, "n_thread": N_THREAD,
        "statuses": dict(collections.Counter(r["status"] for r in out)),
        "overall": {
            "parsed_ok": len(ok),
            "old_hit": sum(r["old_hit"] for r in ok),
            "new_hit": sum(r["new_hit"] for r in ok),
            "tiers": dict(collections.Counter(str(r["tier"]) for r in ok)),
        },
        "parse_ms": {"p50": round((pct(tp, .5) or 0) * 1000, 2),
                     "p95": round((pct(tp, .95) or 0) * 1000, 2),
                     "p99": round((pct(tp, .99) or 0) * 1000, 2),
                     "mean": round(sum(tp) / len(tp) * 1000, 2) if tp else None},
        "tags": {"p50": pct(tags, .5), "p95": pct(tags, .95), "p99": pct(tags, .99)},
        "by_crawl_group": {"%s|%s" % k: dict(v) for k, v in sorted(cell.items())},
        "by_source_crawl": {"%s|%s" % k: dict(v) for k, v in sorted(by_source.items())},
        "caveat": ("spider parse_html hooks excluded - they need scrapy and "
                   "per-spider config, cover 0.4% of records and none of the "
                   "top 20 sources"),
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # ---- readable summary to stdout ----
    print("\n%-20s %6s %6s %8s %8s" % ("crawl", "n", "ok", "old%", "new%"))
    for k in sorted(cell):
        c = cell[k]
        n = c["n"] or 1
        okc = c["ok"] or 1
        print("%-20s %6d %6d %7.1f%% %7.1f%%" % (
            "%s|%s" % k, c["n"], c["ok"],
            100 * c["old_hit"] / okc, 100 * c["new_hit"] / okc))

    blob = json.dumps(result, indent=2, default=str)
    print("=== PARSE PROBE RESULT ===")
    print(blob[:2000])
    try:
        iid = imds("instance-id")
        result["instance_id"] = iid
        blob = json.dumps(result, indent=2, default=str)
    except Exception:
        iid = None
    try:
        boto3.client("s3").put_object(
            Bucket=OUT_BUCKET, Key=RESULT_KEY,
            Body=blob.encode(), ContentType="application/json")
        print("wrote s3://%s/%s" % (OUT_BUCKET, RESULT_KEY))
    except Exception as ex:
        print("could not write result:", ex)
    if iid:
        try:
            boto3.client("ec2").terminate_instances(InstanceIds=[iid])
            print("self-terminate requested")
        except Exception as ex:
            print("self-terminate failed:", ex)
            os.system("shutdown -h now")


def imds(path):
    tok = urllib.request.urlopen(urllib.request.Request(
        "http://169.254.169.254/latest/api/token", method="PUT",
        headers={"X-aws-ec2-metadata-token-ttl-seconds": "300"}), timeout=5).read().decode()
    return urllib.request.urlopen(urllib.request.Request(
        "http://169.254.169.254/latest/meta-data/" + path,
        headers={"X-aws-ec2-metadata-token": tok}), timeout=5).read().decode()


if __name__ == "__main__":
    main()

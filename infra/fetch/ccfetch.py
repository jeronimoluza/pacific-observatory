"""Fetch the resolved Common Crawl manifests and parse prices in flight.

The resolve stage produced 102 manifests -- 49,165,982 captures over
21,878,737 distinct product pages -- naming a WARC file, offset and length per
capture. This turns those addresses into price rows.

**Parse in flight, keep only the rows.** Storing the raw WARC payload is about
2.6 TB, roughly $61/month at Intelligent-Tiering rates, which burns the account's
$120 balance in two months and triggers an early close that deletes the data
with it. The parsed output is about 5 GB and comes off AWS free under the
100 GB/month egress threshold.

**Generic tiers only, by measurement.** `parse_html` hooks exist for 45.4% of
spiders but those spiders are 0.4% of records -- the highest-volume sources are
bespoke and hookless. Carrying the whole `prices` package (and scrapy, and every
per-spider config) onto the instance to reach 0.4% is not worth the weight, so
this ships the four self-contained tiers: JSON-LD, OpenGraph meta, Next.js
flight data, and inline microdata.

Reading `s3://commoncrawl` is free -- the bucket is `Payer=BucketOwner`,
verified with `GetBucketRequestPayment` rather than assumed -- and sustains
concurrency 64 with zero 403s, against a public CDN that bans the whole host at
around 12.
"""

import concurrent.futures as cf
import gzip
import io
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import boto3
from botocore.config import Config

CC_BUCKET = "commoncrawl"

CONC = int(os.environ.get("CONC", "64"))
OUT_BUCKET = os.environ.get("OUT_BUCKET", "")
OUT_PREFIX = os.environ.get("OUT_PREFIX", "parsed")
MISS_PREFIX = os.environ.get("MISS_PREFIX", "misses")
MANIFEST_BUCKET = os.environ.get("MANIFEST_BUCKET", OUT_BUCKET)
MANIFEST_PREFIX = os.environ.get("MANIFEST_PREFIX", "resolve/manifests")
SHARD = int(os.environ.get("SHARD", "0"))
NSHARDS = int(os.environ.get("NSHARDS", "1"))
WORK = os.environ.get("WORK", "/tmp/ccfetch")
# A run that has already written its object is not repeated. Crawl-major and
# one object per (crawl, shard), so a killed instance resumes at crawl grain.
RESUME = os.environ.get("RESUME", "1") != "0"

_CHARSET_HDR = re.compile(rb"charset\s*=\s*[\"']?([\w\-]+)", re.I)
_CHARSET_META = re.compile(rb"charset\s*=\s*[\"']?([\w\-]+)", re.I)

_cfg = Config(
    max_pool_connections=CONC + 16,
    retries={"max_attempts": 8, "mode": "adaptive"},
    read_timeout=90,
    connect_timeout=20,
)
_s3 = boto3.client("s3", config=_cfg)

sys.path.insert(0, os.environ.get("PARSE_DIR", "/tmp/parse"))
from archived import row_from_meta, rows_from_jsonld  # noqa: E402
from archived_embedded import rows_from_next_flight  # noqa: E402
from archived_microdata import rows_from_microdata  # noqa: E402


# ----------------------------------------------------------------- WARC layer

def split_warc(raw):
    """``(http_headers, body)``, or ``(None, reason)``."""
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
    return blob[i + 4:j], body


def decode(headers, body):
    """Text, preferring the charset the page declares.

    Old captures are routinely Shift_JIS, Big5, EUC-KR or windows-1251. Decoding
    those as latin-1 does not raise -- it silently produces mojibake, which
    reaches the product name and is unrecoverable downstream.
    """
    m = _CHARSET_HDR.search(headers or b"") or _CHARSET_META.search(body[:4096])
    if m:
        cs = m.group(1).decode("ascii", "ignore").lower()
        if cs.replace("_", "-") not in ("utf-8", "utf8"):
            try:
                return body.decode(cs)
            except (UnicodeDecodeError, LookupError):
                pass
    for enc in ("utf-8", "latin-1"):
        try:
            return body.decode(enc)
        except UnicodeDecodeError:
            continue
    return body.decode("utf-8", "replace")


# ---------------------------------------------------------------- parse layer

def parse_rows(html, url):
    """The four spider-independent tiers, in measured yield order.

    Microdata is last: it was measured only on pages the tiers above already
    fail, so appending it cannot change a page that parses today.
    """
    rows = rows_from_jsonld(html, url)
    if rows:
        return rows, "jsonld"
    row = row_from_meta(html, url)
    if row:
        return [row], "meta"
    rows = rows_from_next_flight(html, url)
    if rows:
        return rows, "flight"
    rows = rows_from_microdata(html, url)
    if rows:
        return rows, "microdata"
    return [], "none"


def to_iso(ts):
    """CC's ``YYYYMMDDHHMMSS`` capture stamp as UTC ISO 8601.

    This is the whole point of the exercise: stamping ``now()`` instead would
    collapse every historical observation onto today and destroy the series.
    """
    try:
        dt = datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None
    return dt.isoformat()


# ---------------------------------------------------------------- fetch layer

class Ban(Exception):
    """Sustained 403s: stop the crawl rather than write a hole into the data."""


def fetch_one(rec, state):
    key = rec.get("filename")
    try:
        off = int(rec["offset"])
        length = int(rec["length"])
    except (KeyError, TypeError, ValueError):
        return None, "bad_record"
    if not key:
        return None, "bad_record"
    rng = "bytes=%d-%d" % (off, off + length - 1)
    try:
        raw = _s3.get_object(Bucket=CC_BUCKET, Key=key, Range=rng)["Body"].read()
    except Exception as exc:
        name = type(exc).__name__
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
        if code in ("AccessDenied", "403") or "403" in str(exc):
            # Checked per record, not per batch: a ban that is only noticed at
            # the end of a run looks exactly like a crawl with no data.
            state["s403"] += 1
            if state["s403"] >= 25:
                raise Ban("25 consecutive 403s from %s" % CC_BUCKET)
        return None, "get_failed:%s%s" % (name, "/" + code if code else "")
    state["s403"] = 0

    headers, body = split_warc(raw)
    if headers is None:
        return None, body
    html = decode(headers, body)
    rows, tier = parse_rows(html, rec["url"])
    if not rows:
        return None, "no_extract"

    stamp = to_iso(rec.get("timestamp", ""))
    out = []
    for row in rows:
        row = dict(row)
        row["scraped_at_utc"] = stamp
        row["source"] = rec.get("spider")
        row["cc_timestamp"] = rec.get("timestamp")
        row["parse_tier"] = tier
        out.append(row)
    return out, tier


# ------------------------------------------------------------------ manifests

def iter_manifest(index):
    """Records for this shard of one crawl's manifest, streamed from S3.

    Streamed rather than downloaded whole: the largest manifest is 96 MB
    compressed and the instances have 4-8 GB of RAM shared with the parser.
    """
    key = "%s/%s.jsonl.gz" % (MANIFEST_PREFIX, index)
    body = _s3.get_object(Bucket=MANIFEST_BUCKET, Key=key)["Body"]
    with gzip.open(io.BytesIO(body.read()), "rt", encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if NSHARDS > 1 and i % NSHARDS != SHARD:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def already_done(out_key):
    if not (RESUME and OUT_BUCKET):
        return False
    try:
        # list, not head-object: the aws-mcp proxy served a stale 404 for 90
        # minutes on an object that existed the whole time.
        resp = _s3.list_objects_v2(Bucket=OUT_BUCKET, Prefix=out_key, MaxKeys=1)
    except Exception:
        return False
    return any(o["Key"] == out_key for o in resp.get("Contents", []))


def miss_row(rec, reason):
    """A miss, recorded at its WARC address so it can be re-read later.

    The raw payload is discarded in flight, so a page that parses to nothing is
    gone unless its address survives. Keeping filename/offset/length means a
    future parser can be tried against exactly these captures for cents, rather
    than by repeating the whole run.
    """
    return {
        "url": rec.get("url"),
        "filename": rec.get("filename"),
        "offset": rec.get("offset"),
        "length": rec.get("length"),
        "timestamp": rec.get("timestamp"),
        "source": rec.get("spider"),
        "reason": reason,
    }


# ----------------------------------------------------------------------- main

def run_crawl(index):
    out_key = "%s/%s/shard-%02d.jsonl.gz" % (OUT_PREFIX, index, SHARD)
    miss_key = "%s/%s/shard-%02d.jsonl.gz" % (MISS_PREFIX, index, SHARD)
    if already_done(out_key):
        print("%-20s skip (already written)" % index, flush=True)
        return 0
    os.makedirs(WORK, exist_ok=True)
    dst = os.path.join(WORK, "%s-%02d.jsonl.gz" % (index, SHARD))
    mdst = os.path.join(WORK, "%s-%02d.miss.jsonl.gz" % (index, SHARD))

    t0 = time.time()
    state = {"s403": 0}
    n = {"rec": 0, "row": 0, "miss": 0}
    tiers = {}
    banned = False

    with gzip.open(dst, "wt", encoding="utf-8") as fh, \
            gzip.open(mdst, "wt", encoding="utf-8") as mfh:

        def consume(fut, rec):
            """Fold one finished future into rows or misses. Ban propagates."""
            n["rec"] += 1
            try:
                rows, tier = fut.result()
            except Ban:
                raise
            except Exception as exc:
                tier = "error:%s" % type(exc).__name__
                tiers[tier] = tiers.get(tier, 0) + 1
                mfh.write(json.dumps(miss_row(rec, tier)) + "\n")
                n["miss"] += 1
                return
            tiers[tier] = tiers.get(tier, 0) + 1
            if rows:
                for row in rows:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                    n["row"] += 1
            else:
                mfh.write(json.dumps(miss_row(rec, tier)) + "\n")
                n["miss"] += 1

        with cf.ThreadPoolExecutor(max_workers=CONC) as pool:
            pending = {}
            for rec in iter_manifest(index):
                pending[pool.submit(fetch_one, rec, state)] = rec
                if len(pending) < CONC * 8:
                    continue
                done, _ = cf.wait(pending, return_when=cf.FIRST_COMPLETED)
                for fut in done:
                    try:
                        consume(fut, pending.pop(fut))
                    except Ban as exc:
                        print("%-20s BAN: %s" % (index, exc), flush=True)
                        banned = True
                        break
                if banned:
                    break
            for fut in cf.as_completed(pending):
                try:
                    consume(fut, pending[fut])
                except Ban as exc:
                    print("%-20s BAN: %s" % (index, exc), flush=True)
                    banned = True
                    break

    dt = time.time() - t0
    top = sorted(tiers.items(), key=lambda kv: -kv[1])[:6]
    print("%-20s recs=%-8d rows=%-8d miss=%-8d %6.0fs %5.1f rec/s  %s"
          % (index, n["rec"], n["row"], n["miss"], dt,
             n["rec"] / dt if dt else 0, dict(top)),
          flush=True)

    if banned:
        # An incomplete shard must not be uploaded: a short object is
        # indistinguishable from a crawl that genuinely held little.
        print("%-20s NOT uploading, run was banned mid-crawl" % index, flush=True)
        return 1
    if OUT_BUCKET:
        _s3.upload_file(dst, OUT_BUCKET, out_key)
        _s3.upload_file(mdst, OUT_BUCKET, miss_key)
        os.remove(dst)
        os.remove(mdst)
    return 0


def main():
    crawls = [c for c in os.environ.get("CRAWLS", "").split(",") if c]
    if not crawls:
        print("no CRAWLS given")
        return 1
    print("crawls=%d shard=%d/%d conc=%d out=s3://%s/%s"
          % (len(crawls), SHARD, NSHARDS, CONC, OUT_BUCKET, OUT_PREFIX),
          flush=True)
    rc = 0
    for index in crawls:
        try:
            rc |= run_crawl(index)
        except Exception as exc:
            print("%-20s FAILED: %r" % (index, exc), flush=True)
            rc = 1
    print("DONE rc=%d" % rc, flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())

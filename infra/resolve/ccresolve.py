"""Resolve Common Crawl cdx indexes to price manifests, block-major, over S3.

Same output as `prices.cc_resolve.resolve_index` — one JSONL row per
(source, record) carrying url/timestamp/filename/offset/length/digest/spider —
reached by a different traversal.

The shipped path is source-major within a crawl: it calls `query_prefix` once
per source, and each call range-fetches the cdx blocks that source's prefix
spans. Sources whose prefixes land in the same block make that block get
fetched again per source. Here the block set is unioned across all 623 sources
first, so **every block is fetched exactly once** and matched against only the
prefixes that can occur in it.

Two properties this relies on, both from the measured Stage 1 probe:
`s3://commoncrawl` is Payer=BucketOwner so the reads are free, and it sustains
concurrency 64 with zero 403s — unlike the public CDN, which IP-bans at ~12.

Ordering differs from the shipped writer (block-major, not source-major). The
fetch side keys off filename/offset and never reads order, and `verify.py`
compares against an existing manifest as a multiset for exactly this reason.
"""

import bisect
import concurrent.futures as cf
import gzip
import io
import json
import os
import re
import sys
import time
from urllib.parse import urlparse

import boto3
from botocore.config import Config

CC_BUCKET = "commoncrawl"
IDX_TMPL = "cc-index/collections/%s/indexes/%s"

CONC = int(os.environ.get("CONC", "64"))
OUT_BUCKET = os.environ.get("OUT_BUCKET", "")
OUT_PREFIX = os.environ.get("OUT_PREFIX", "resolve")

_s3 = boto3.client(
    "s3",
    config=Config(
        max_pool_connections=CONC + 16,
        retries={"max_attempts": 6, "mode": "adaptive"},
        read_timeout=90,
        connect_timeout=20,
    ),
)


def _get(key, rng=None):
    kw = {"Bucket": CC_BUCKET, "Key": key}
    if rng:
        kw["Range"] = rng
    return _s3.get_object(**kw)["Body"].read()


def load_sources(path):
    """(surt, compiled path_re, spider) per source, sorted by surt.

    Sorted so the block->candidate mapping can be built by bisecting the same
    way the cluster index is searched.
    """
    out = []
    for c in json.load(open(path)):
        out.append((c["surt"], re.compile(c["path_re"] or ""), c["spider"]))
    out.sort(key=lambda t: t[0])
    return out


def load_cluster(index):
    """(keys, blocks) for one crawl's cluster.idx, read straight from S3."""
    raw = _get(IDX_TMPL % (index, "cluster.idx"))
    keys, blocks = [], []
    for line in raw.decode("utf-8", "replace").splitlines():
        p = line.rstrip("\n").split("\t")
        if len(p) < 4:
            continue
        try:
            blocks.append((p[1], int(p[2]), int(p[3])))
        except ValueError:
            continue
        keys.append(p[0].split(" ")[0])
    return keys, blocks


def plan(keys, blocks, sources):
    """{(shard, offset, length): [source, ...]} — each block fetched once.

    A prefix's records live in the blocks from the one whose first key sorts at
    or before it, through the last whose key still sorts below `prefix + \\xff`.
    Several prefixes routinely share a block, which is the whole point.
    """
    todo = {}
    for surt, path_re, spider in sources:
        stop = surt + "\xff"
        pos = max(0, bisect.bisect_right(keys, surt) - 1)
        while pos < len(keys) and keys[pos] <= stop:
            todo.setdefault(blocks[pos], []).append((surt, path_re, spider))
            pos += 1
    return todo


def scan_block(block, cands):
    """Rows from one cdx block, for the sources that can appear in it."""
    shard, offset, length = block
    raw = _get(IDX_TMPL % (scan_block.index, shard),
               "bytes=%d-%d" % (offset, offset + length - 1))
    text = gzip.GzipFile(fileobj=io.BytesIO(raw)).read().decode("utf-8", "replace")
    rows = []
    for line in text.split("\n"):
        if not line:
            continue
        hit = [c for c in cands if line.startswith(c[0])]
        if not hit:
            continue
        # cdx line: "<surt> <timestamp> <json>" — the capture timestamp is the
        # second field, not a key inside the JSON payload.
        fields = line.split(" ", 2)
        if len(fields) < 3:
            continue
        try:
            payload = json.loads(fields[2])
        except json.JSONDecodeError:
            continue
        if payload.get("status") != "200":
            continue
        url = payload.get("url", "")
        try:
            path = urlparse(url).path
        except ValueError:
            continue
        try:
            rec_offset = int(payload["offset"])
            rec_length = int(payload["length"])
        except (KeyError, ValueError):
            continue
        base = {
            "url": url,
            "timestamp": fields[1],
            "filename": payload.get("filename", ""),
            "offset": rec_offset,
            "length": rec_length,
            "digest": payload.get("digest", ""),
        }
        for _surt, path_re, spider in hit:
            try:
                if not path_re.search(path):
                    continue
            except ValueError:
                continue
            row = dict(base)
            row["spider"] = spider
            rows.append(row)
    return rows


def resolve(index, sources, out_dir="/tmp"):
    t0 = time.time()
    keys, blocks = load_cluster(index)
    todo = plan(keys, blocks, sources)
    scan_block.index = index
    dst = os.path.join(out_dir, "%s.jsonl.gz" % index)
    n = 0
    errs = 0
    with gzip.open(dst, "wt", encoding="utf-8") as fh:
        with cf.ThreadPoolExecutor(max_workers=CONC) as pool:
            futs = {pool.submit(scan_block, b, c): b for b, c in todo.items()}
            for fut in cf.as_completed(futs):
                try:
                    rows = fut.result()
                except Exception as exc:  # one bad block must not lose a crawl
                    errs += 1
                    if errs <= 5:
                        print("  block %s failed: %s" % (futs[fut][0], exc),
                              flush=True)
                    continue
                for row in rows:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                    n += 1
    dt = time.time() - t0
    print("%-20s blocks=%-6d rows=%-9d errs=%-4d %6.1fs  %s"
          % (index, len(todo), n, errs, dt,
             "%.0f blk/s" % (len(todo) / dt) if dt else ""), flush=True)
    return dst, n, len(todo), errs


def main():
    src_path = os.environ.get("SOURCES", "/tmp/sources.json")
    crawls = [c for c in os.environ.get("CRAWLS", "").split(",") if c]
    if not crawls:
        print("no CRAWLS given")
        return 1
    sources = load_sources(src_path)
    print("sources=%d crawls=%d conc=%d" % (len(sources), len(crawls), CONC),
          flush=True)
    total = 0
    for index in crawls:
        try:
            dst, n, _nb, _errs = resolve(index, sources)
        except Exception as exc:
            print("%-20s FAILED: %s" % (index, exc), flush=True)
            continue
        total += n
        if OUT_BUCKET:
            _s3.upload_file(dst, OUT_BUCKET,
                            "%s/%s.jsonl.gz" % (OUT_PREFIX, index))
            os.remove(dst)
    print("TOTAL rows=%d" % total, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

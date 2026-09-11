"""Resolve r9's 18 sources locally: block-major, cached cluster.idx, CDN blocks.

The fleet's resolver reads s3://commoncrawl, which is free from EC2 -- but the
account's 16 vCPU are all committed to the r8b fetch, so this runs on the laptop
instead. All 102 cluster.idx files are already cached here, so only the cdx
blocks cross the network, and the CDN cap of 4 concurrent workers applies.

Output matches the fleet's manifest schema exactly (one JSONL row per capture,
gzipped, one file per crawl) so ccfetch can consume it unchanged.
"""
import bisect, gzip, json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

TMP = "/Users/jeronimoluza/.claude/jobs/b56b459b/tmp"
sys.path.insert(0, "/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo/src")
from prices import cc_index

OUT = f"{TMP}/manifests-r9"
os.makedirs(OUT, exist_ok=True)
CRAWLS = [l.strip() for l in open(f"{TMP}/crawls.txt") if l.strip()]
SRC = [(s["surt"], re.compile(s["path_re"] or ""), s["spider"])
       for s in json.load(open(f"{TMP}/sources-r9.json"))]
SRC.sort(key=lambda t: t[0])

def plan(keys, blocks):
    todo = {}
    for surt, rx, spider in SRC:
        stop = surt + "\xff"
        pos = max(0, bisect.bisect_right(keys, surt) - 1)
        while pos < len(keys) and keys[pos] <= stop:
            todo.setdefault(blocks[pos], []).append((surt, rx, spider))
            pos += 1
    return todo

t0 = time.time()
grand = 0
for ci, crawl in enumerate(CRAWLS, 1):
    dst = f"{OUT}/{crawl}.jsonl.gz"
    if os.path.exists(dst):
        continue
    keys, blocks = cc_index.load_cluster(crawl)
    todo = plan(keys, blocks)

    def scan(item):
        block, cands = item
        shard, off, ln = block
        try:
            text = cc_index._fetch_block(crawl, shard, off, ln)
        except Exception:
            return []
        rows = []
        for line in text.split("\n"):
            if not line:
                continue
            hit = [c for c in cands if line.startswith(c[0])]
            if not hit:
                continue
            f = line.split(" ", 2)
            if len(f) < 3:
                continue
            try:
                pl = json.loads(f[2])
            except json.JSONDecodeError:
                continue
            # Absent status means unknown, not non-200: CC-MAIN-2015-06/-11 ship
            # no status key at all and a bare != "200" empties those manifests.
            st = pl.get("status")
            if st is not None and st != "200":
                continue
            url = pl.get("url", "")
            try:
                path = urlparse(url).path
            except ValueError:
                continue
            for surt, rx, spider in hit:
                if not rx.search(path):
                    continue
                try:
                    rows.append({"url": url, "timestamp": f[1],
                                 "filename": pl.get("filename", ""),
                                 "offset": int(pl["offset"]),
                                 "length": int(pl["length"]),
                                 "digest": pl.get("digest", ""),
                                 "spider": spider})
                except (KeyError, ValueError):
                    pass
                break
        return rows

    n = 0
    with gzip.open(dst + ".part", "wt", encoding="utf-8") as fh:
        with ThreadPoolExecutor(max_workers=4) as ex:
            for rows in ex.map(scan, todo.items()):
                for r in rows:
                    fh.write(json.dumps(r) + "\n")
                    n += 1
    os.replace(dst + ".part", dst)
    grand += n
    print(f"[{ci:3d}/{len(CRAWLS)}] {crawl:22s} blocks={len(todo):4d} rows={n:7d} "
          f"total={grand:8d} {time.time()-t0:6.0f}s", flush=True)

print(f"\nDONE {grand} rows across {len(CRAWLS)} crawls in {time.time()-t0:.0f}s")

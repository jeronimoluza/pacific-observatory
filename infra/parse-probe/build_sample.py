"""Stratified probe sample: top sources by RECORD VOLUME x capture year.

Coverage is measured per record, not per spider, because spider-count coverage
and record coverage are nearly inverted (45.4% of spiders is 0.4% of records).
"""
import json
import glob
import gzip
import os
import random
import collections

D = ("/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo/data/prices/"
     "_cc_manifests/by_index/")
OUT = "/Users/jeronimoluza/.claude/jobs/f8501cf5/tmp/probe_sample.jsonl.gz"

TOP_N = 20          # head sources, tracked individually
PER_CELL = 60       # records per (head source, crawl)
TAIL_PER_CRAWL = 250  # random records from every other source, per crawl

random.seed(20260827)

# pass 1: total volume per source
vol = collections.Counter()
for f in sorted(glob.glob(D + "*.jsonl")):
    for line in open(f):
        try:
            vol[json.loads(line)["spider"]] += 1
        except Exception:
            pass
total = sum(vol.values())
head = [s for s, _ in vol.most_common(TOP_N)]
head_set = set(head)
head_share = sum(vol[s] for s in head) / total
print("head sources: %d covering %.1f%% of all records" % (len(head), 100 * head_share))

# pass 2: reservoir sample per (source-or-TAIL, crawl)
cells = collections.defaultdict(list)
seen = collections.Counter()
for f in sorted(glob.glob(D + "*.jsonl")):
    crawl = os.path.basename(f)[:-6]
    for line in open(f):
        try:
            r = json.loads(line)
        except Exception:
            continue
        sp = r["spider"]
        key = (sp if sp in head_set else "__TAIL__", crawl)
        cap = PER_CELL if sp in head_set else TAIL_PER_CRAWL
        seen[key] += 1
        buf = cells[key]
        if len(buf) < cap:
            buf.append(r)
        else:                                   # reservoir: uniform over the cell
            j = random.randrange(seen[key])
            if j < cap:
                buf[j] = r

rows = []
for (src, crawl), buf in sorted(cells.items()):
    for r in buf:
        rows.append({
            "u": r["url"], "t": r["timestamp"], "f": r["filename"],
            "o": r["offset"], "l": r["length"],
            "s": r["spider"], "c": crawl,
            "g": "head" if src != "__TAIL__" else "tail",
        })
random.shuffle(rows)                            # spread load across segments

with gzip.open(OUT, "wt") as fh:
    for r in rows:
        fh.write(json.dumps(r) + "\n")

by_crawl = collections.Counter(r["c"] for r in rows)
print("sampled records: %s  cells: %d" % ("{:,}".format(len(rows)), len(cells)))
print("bytes to fetch: %s" % "{:,}".format(sum(r["l"] for r in rows)))
print("payload: %s bytes gz" % "{:,}".format(os.path.getsize(OUT)))
print("\n%-20s %8s" % ("crawl", "sampled"))
for c in sorted(by_crawl):
    print("%-20s %8d" % (c, by_crawl[c]))
print("\nhead sources:", ", ".join(head[:10]))

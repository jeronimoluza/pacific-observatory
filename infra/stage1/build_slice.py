import gzip, json, base64, re

SRC = "/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo/data/prices/_cc_manifests/by_index/CC-MAIN-2024-26.jsonl"
PAT = re.compile(
    r"^crawl-data/(CC-MAIN-[\d-]+)/segments/([^/]+)/warc/"
    r"CC-MAIN-(\d+)-(\d+)-(\d+)\.warc\.gz$"
)

segs, seg_ix, recs = [], {}, []
crawl = None
with open(SRC) as f:
    for i, line in enumerate(f):
        if i % 337:
            continue
        r = json.loads(line)
        m = PAT.match(r["filename"])
        if not m:
            continue
        crawl, seg, s, e, part = m.groups()
        key = "%s|%s|%s" % (seg, s, e)
        if key not in seg_ix:
            seg_ix[key] = len(segs)
            segs.append(key)
        recs.append([seg_ix[key], int(part), r["offset"], r["length"]])
        if len(recs) >= 1000:
            break

blob = {"c": crawl, "s": segs, "r": recs}
raw = json.dumps(blob, separators=(",", ":")).encode()
b64 = base64.b64encode(gzip.compress(raw, 9)).decode()

total = sum(r[3] for r in recs)
print("records:", len(recs), "| segments:", len(segs))
print("bytes to fetch:", total, "| mean:", total // len(recs))
print("gzip+b64 chars:", len(b64))

with open("/Users/jeronimoluza/.claude/jobs/f8501cf5/tmp/slice.b64", "w") as fh:
    fh.write(b64)

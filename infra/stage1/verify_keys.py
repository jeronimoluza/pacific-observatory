import base64, gzip, json, re

TMP = "/Users/jeronimoluza/.claude/jobs/f8501cf5/tmp"
SRC = ("/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo/data/prices/"
       "_cc_manifests/by_index/CC-MAIN-2024-26.jsonl")

d = json.loads(gzip.decompress(base64.b64decode(open(TMP + "/slice.b64").read().strip())))
crawl, segs, recs = d["c"], d["s"], d["r"]


def key_of(r):
    seg, s, e = segs[r[0]].split("|")
    return "crawl-data/%s/segments/%s/warc/CC-MAIN-%s-%s-%05d.warc.gz" % (
        crawl, seg, s, e, r[1],
    )


# rebuild the same stride sample from the manifest and compare field by field
expected = []
PAT = re.compile(r"^crawl-data/(CC-MAIN-[\d-]+)/segments/([^/]+)/warc/"
                 r"CC-MAIN-(\d+)-(\d+)-(\d+)\.warc\.gz$")
with open(SRC) as f:
    for i, line in enumerate(f):
        if i % 337:
            continue
        r = json.loads(line)
        if not PAT.match(r["filename"]):
            continue
        expected.append((r["filename"], r["offset"], r["length"]))
        if len(expected) >= len(recs):
            break

bad = 0
for got, exp in zip(recs, expected):
    k = key_of(got)
    if (k, got[2], got[3]) != exp:
        bad += 1
        if bad <= 3:
            print("MISMATCH\n  got %s off=%s len=%s\n  exp %s off=%s len=%s"
                  % (k, got[2], got[3], exp[0], exp[1], exp[2]))

print("compared:", len(recs))
print("mismatches:", bad)
print("PASS" if bad == 0 else "FAIL")
print("sample key:", key_of(recs[0]))

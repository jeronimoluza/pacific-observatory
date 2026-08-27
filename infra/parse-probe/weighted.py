"""Reweight the stratified probe result by true record volume per (crawl, group)."""
import json
import glob
import os
import collections

D = ("/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo/data/prices/"
     "_cc_manifests/by_index/")
R = json.load(open("/Users/jeronimoluza/.claude/jobs/f8501cf5/tmp/result.json"))

vol = collections.Counter()
for f in sorted(glob.glob(D + "*.jsonl")):
    for line in open(f):
        try:
            vol[json.loads(line)["spider"]] += 1
        except Exception:
            pass
HEAD = set(s for s, _ in vol.most_common(20))

# true volume per (crawl, group)
truev = collections.Counter()
for f in sorted(glob.glob(D + "*.jsonl")):
    crawl = os.path.basename(f)[:-6]
    for line in open(f):
        try:
            sp = json.loads(line)["spider"]
        except Exception:
            continue
        truev[(crawl, "head" if sp in HEAD else "tail")] += 1

rate = {}
for key, c in R["by_crawl_group"].items():
    crawl, grp = key.rsplit("|", 1)
    ok = c.get("ok", 0)
    if ok:
        rate[(crawl, grp)] = (c.get("new_hit", 0) / ok, c.get("tier_selectors", 0) / ok)

TOT = sum(truev.values())
print("total records in resolved manifests: {:,}".format(TOT))
print()
print("%-18s %12s %8s %8s %14s" % ("crawl", "records", "new%", "old_use%", "expected rows"))
gtot = gnew = gold = 0
for crawl in sorted(set(c for c, _ in truev)):
    n = new = old = 0
    for grp in ("head", "tail"):
        v = truev.get((crawl, grp), 0)
        if not v or (crawl, grp) not in rate:
            continue
        r, s = rate[(crawl, grp)]
        n += v
        new += v * r
        old += v * s
    if not n:
        continue
    gtot += n
    gnew += new
    gold += old
    print("%-18s %12s %7.1f%% %7.1f%% %14s" % (
        crawl, "{:,}".format(n), 100 * new / n, 100 * old / n,
        "{:,}".format(int(new))))

print()
print("VOLUME-WEIGHTED across all 22 resolved crawls")
print("  records                     {:>14}".format("{:,}".format(gtot)))
print("  usable rows, fixed ladder   {:>14}  ({:.1f}%)".format(
    "{:,}".format(int(gnew)), 100 * gnew / gtot))
print("  usable rows, selectors only {:>14}  ({:.1f}%)".format(
    "{:,}".format(int(gold)), 100 * gold / gtot))
print("  multiplier from the fix     {:>14.2f}x".format(gnew / gold if gold else 0))

# era split
early = sum(v for (c, g), v in truev.items() if c < "CC-MAIN-2016")
print()
print("records in crawls before 2016: {:,} ({:.1f}% of resolved volume)".format(
    early, 100 * early / TOT))

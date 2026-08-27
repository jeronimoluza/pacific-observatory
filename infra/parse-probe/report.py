import json
import collections
import math

R = json.load(open("/Users/jeronimoluza/.claude/jobs/f8501cf5/tmp/result.json"))


def ci(k, n):
    """Wilson 95% half-width, in percentage points."""
    if not n:
        return 0.0
    p = k / n
    z = 1.96
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    hw = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return 100 * hw, 100 * c


print("=" * 74)
print("PARSE YIELD BY CAPTURE YEAR  (head = top-20 sources by volume, tail = rest)")
print("=" * 74)
print("%-18s %6s %7s %7s %8s   %6s %7s %7s" % (
    "crawl", "n", "old%", "new%", "gain", "n", "old%", "new%"))
print("%-18s %6s %7s %7s %8s   %6s %7s %7s" % (
    "", "head", "", "", "", "tail", "", ""))

rows = collections.defaultdict(dict)
for key, c in R["by_crawl_group"].items():
    crawl, grp = key.rsplit("|", 1)
    rows[crawl][grp] = c

for crawl in sorted(rows):
    g = rows[crawl]
    out = []
    for grp in ("head", "tail"):
        c = g.get(grp, {})
        ok = c.get("ok", 0)
        if not ok:
            out.append((0, None, None))
            continue
        out.append((ok, 100 * c.get("old_hit", 0) / ok, 100 * c.get("new_hit", 0) / ok))
    h, t = out
    gain = (h[2] - h[1]) if h[1] is not None else 0
    print("%-18s %6d %6.1f%% %6.1f%% %+7.1f   %6d %6.1f%% %6.1f%%" % (
        crawl, h[0], h[1] or 0, h[2] or 0, gain,
        t[0], t[1] or 0, t[2] or 0))

# pooled by year across both groups
print()
print("=" * 74)
print("POOLED BY CRAWL (both groups), with 95% CI on the new hit rate")
print("=" * 74)
print("%-18s %8s %8s %8s %10s" % ("crawl", "n", "old%", "new%", "95% CI"))
for crawl in sorted(rows):
    n = sum(c.get("ok", 0) for c in rows[crawl].values())
    old = sum(c.get("old_hit", 0) for c in rows[crawl].values())
    new = sum(c.get("new_hit", 0) for c in rows[crawl].values())
    hw, cen = ci(new, n)
    print("%-18s %8d %7.1f%% %7.1f%%   +/-%4.1f" % (
        crawl, n, 100 * old / n, 100 * new / n, hw))

# which tier carries each era
print()
print("=" * 74)
print("WHICH TIER PRODUCED THE ROW, by crawl (head+tail)")
print("=" * 74)
tiers = ["tier_jsonld", "tier_meta", "tier_selectors", "tier_next_flight",
         "tier_selectors_noprice", "tier_None"]
print("%-18s %8s %7s %7s %7s %8s %7s" % (
    "crawl", "n", "jsonld", "meta", "select", "nextfl", "MISS"))
for crawl in sorted(rows):
    agg = collections.Counter()
    for c in rows[crawl].values():
        for t in tiers:
            agg[t] += c.get(t, 0)
    n = sum(c.get("ok", 0) for c in rows[crawl].values())
    print("%-18s %8d %6.1f%% %6.1f%% %6.1f%% %6.1f%% %7.1f%%" % (
        crawl, n,
        100 * agg["tier_jsonld"] / n, 100 * agg["tier_meta"] / n,
        100 * agg["tier_selectors"] / n, 100 * agg["tier_next_flight"] / n,
        100 * (agg["tier_None"] + agg["tier_selectors_noprice"]) / n))

"""Volume-weight the autopsy: what would the candidate tiers be worth in production?

The sample is stratified by source volume x era, so its raw rates are not the
production rates. Reweighting by each source's true record count in the
resolved manifests turns "converted 1,884 of 12,603 sampled misses" into an
expected row count over the 9,297,137 records we hold.
"""
import collections
import glob
import json
import os

D = ("/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo/data/prices/"
     "_cc_manifests/by_index/")
R = json.load(open("/Users/jeronimoluza/.claude/jobs/f8501cf5/tmp/autopsy_result.json"))

vol = collections.Counter()
for f in sorted(glob.glob(D + "*.jsonl")):
    for line in open(f):
        try:
            vol[json.loads(line)["spider"]] += 1
        except Exception:
            pass
TOT = sum(vol.values())

bs = R["by_source"]
covered = sum(vol[s] for s in bs if s in vol)
print("records in resolved manifests      {:>14,}".format(TOT))
print("records from sources in the sample {:>14,}  ({:.1f}%)".format(
    covered, 100 * covered / TOT))
print()

hit = conv = 0.0
for s, c in bs.items():
    v = vol.get(s, 0)
    n = c.get("ok", 0)
    if not v or not n:
        continue
    hit += v * c.get("hit", 0) / n
    conv += v * c.get("conv_ANY", 0) / n

print("VOLUME-WEIGHTED over the {:,} records those sources carry".format(covered))
print("  usable rows, shipped ladder   {:>14,}  ({:.1f}%)".format(
    int(hit), 100 * hit / covered))
print("  extra rows from the candidates{:>14,}  (+{:.1f} pts)".format(
    int(conv), 100 * conv / covered))
print("  usable rows, with candidates  {:>14,}  ({:.1f}%)".format(
    int(hit + conv), 100 * (hit + conv) / covered))
print("  relative gain                 {:>14.2f}x".format(
    (hit + conv) / hit if hit else 0))
print()

# per-tier share of the conversions, scaled the same way
tiers = collections.Counter()
for s, c in bs.items():
    v, n = vol.get(s, 0), c.get("ok", 0)
    if not v or not n:
        continue
    tiers["conv_ANY"] += v * c.get("conv_ANY", 0) / n
raw = R["converted"]
print("candidate mix (raw sample counts, ANY={}):".format(raw["ANY"]))
for k in ("microdata", "namefill", "charset", "rdfa"):
    print("  %-10s %6d   %5.1f%% of conversions" % (
        k, raw.get(k, 0), 100 * raw.get(k, 0) / raw["ANY"]))
print()

print("TOP SOURCES BY EXPECTED EXTRA ROWS")
rows = []
for s, c in bs.items():
    v, n = vol.get(s, 0), c.get("ok", 0)
    if not v or not n or not c.get("conv_ANY"):
        continue
    rows.append((v * c["conv_ANY"] / n, s, v, 100 * c["hit"] / n,
                 100 * (c["hit"] + c["conv_ANY"]) / n, n))
rows.sort(reverse=True)
print("%-20s %12s %8s %8s %7s %6s" % (
    "source", "records", "now%", "with%", "extra", "n"))
for extra, s, v, now, wi, n in rows[:15]:
    print("%-20s %12s %7.1f%% %7.1f%% %7s %6d" % (
        s, "{:,}".format(v), now, wi, "{:,}".format(int(extra)), n))

print()
early = [c for k, c in R["by_crawl"].items() if k < "CC-MAIN-2020"]
n = sum(c.get("ok", 0) for c in early)
h = sum(c.get("hit", 0) for c in early)
cv = sum(c.get("conv_ANY", 0) for c in early)
print("PRE-2020 SAMPLE (unweighted): n=%d  hit %.1f%% -> %.1f%%  (%.2fx)" % (
    n, 100 * h / n, 100 * (h + cv) / n, (h + cv) / h))
late = [c for k, c in R["by_crawl"].items() if k >= "CC-MAIN-2023"]
n2 = sum(c.get("ok", 0) for c in late)
h2 = sum(c.get("hit", 0) for c in late)
cv2 = sum(c.get("conv_ANY", 0) for c in late)
print("2023+ SAMPLE     (unweighted): n=%d  hit %.1f%% -> %.1f%%  (%.2fx)" % (
    n2, 100 * h2 / n2, 100 * (h2 + cv2) / n2, (h2 + cv2) / h2))

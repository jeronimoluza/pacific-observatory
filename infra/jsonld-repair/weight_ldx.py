"""What is the JSON-LD repair worth over the 9.2M records we hold?

Chains three measured rates per source:
    records in the resolved manifests
  x miss rate           (from the autopsy: miss / pages probed)
  x recovery rate       (from here: conversions / archived miss pages)

The archived miss HTML is only the misses at or under the 400 KB store cap,
so the recovery rate is measured on a subset; the per-source coverage of that
subset is reported alongside so the bias is visible rather than assumed.
"""
import collections
import glob
import json

D = ("/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo/data/prices/"
     "_cc_manifests/by_index/")
T = "/Users/jeronimoluza/.claude/jobs/f8501cf5/tmp/"
A = json.load(open(T + "autopsy_result.json"))
X = json.load(open(T + "ldx/ldx_result.json"))

vol = collections.Counter()
for f in sorted(glob.glob(D + "*.jsonl")):
    for line in open(f):
        try:
            vol[json.loads(line)["spider"]] += 1
        except Exception:
            pass
TOT = sum(vol.values())

ap, xs = A["by_source"], X["by_source"]
rows = []
tot_extra = tot_hit = tot_cov = 0.0
arch_tot = miss_tot = 0
for s, c in ap.items():
    n_ok, n_hit = c.get("ok", 0), c.get("hit", 0)
    n_miss = n_ok - n_hit
    v = vol.get(s, 0)
    if not v or not n_ok:
        continue
    tot_cov += v
    tot_hit += v * n_hit / n_ok
    arch = xs.get(s, {}).get("archived_miss", 0)
    conv = xs.get(s, {}).get("conv", 0)
    arch_tot += arch
    miss_tot += n_miss
    if not arch or not conv or not n_miss:
        continue
    extra = v * (n_miss / n_ok) * (conv / arch)
    tot_extra += extra
    rows.append((extra, s, v, conv, arch, n_miss, 100 * arch / n_miss))

print("records in resolved manifests        {:>14,}".format(TOT))
print("records from sources in the sample   {:>14,} ({:.1f}%)".format(
    int(tot_cov), 100 * tot_cov / TOT))
print()
print("archived miss pages {:,} of {:,} sampled misses ({:.1f}% - "
      "the 400 KB store cap)".format(arch_tot, miss_tot,
                                     100 * arch_tot / miss_tot))
print()
print("VOLUME-WEIGHTED EFFECT OF THE JSON-LD REPAIR")
print("  usable rows today              {:>14,}  ({:.1f}%)".format(
    int(tot_hit), 100 * tot_hit / tot_cov))
print("  extra rows from the repair     {:>14,}  (+{:.2f} pts)".format(
    int(tot_extra), 100 * tot_extra / tot_cov))
print("  usable rows with the repair    {:>14,}  ({:.1f}%)".format(
    int(tot_hit + tot_extra), 100 * (tot_hit + tot_extra) / tot_cov))
print("  relative gain                  {:>14.3f}x".format(
    (tot_hit + tot_extra) / tot_hit))
print()
print("%-22s %13s %6s %6s %8s %9s" % (
    "source", "records", "conv", "arch", "extra", "arch/miss"))
rows.sort(reverse=True)
for extra, s, v, conv, arch, n_miss, cov in rows[:14]:
    print("%-22s %13s %6d %6d %8s %8.0f%%" % (
        s, "{:,}".format(v), conv, arch, "{:,}".format(int(extra)), cov))

print()
bc = X["by_crawl"]
print("BY ERA (sampled pages, unweighted)")
print("%-10s %9s %9s %8s" % ("era", "ld_miss", "conv", "rate"))
for lo, hi, lab in (("CC-MAIN-2013", "CC-MAIN-2020", "pre-2020"),
                    ("CC-MAIN-2020", "CC-MAIN-2023", "2020-22"),
                    ("CC-MAIN-2023", "CC-MAIN-2099", "2023+")):
    m = sum(c.get("ld_miss", 0) for k, c in bc.items() if lo <= k < hi)
    cv = sum(c.get("conv", 0) for k, c in bc.items() if lo <= k < hi)
    print("%-10s %9d %9d %7.1f%%" % (lab, m, cv, 100 * cv / m if m else 0))

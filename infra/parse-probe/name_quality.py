"""Measure name quality of the microdata tier, offline, on archived miss HTML.

The autopsy counted conversions; a conversion whose product_name is a
breadcrumb category ("Music") or a JS variable ("variationId") is not a usable
row, because product_name is what feeds classification. This checks what
fraction of converted rows carry a name that is actually the product's.
"""
import collections
import gzip
import json
import os
import sys

sys.path.insert(0, "/Users/jeronimoluza/.claude/jobs/f8501cf5/tmp/parse_clean")
sys.path.insert(0, "/Users/jeronimoluza/wb/pacificobservatory/repo/pacific-observatory/"
                   ".claude/worktrees/cc-infra-stage0/infra/parse-probe")

os.makedirs("/tmp/parse", exist_ok=True)
for f in ("archived.py", "archived_embedded.py", "selectors_mod.py"):
    src = "/Users/jeronimoluza/.claude/jobs/f8501cf5/tmp/parse_clean/" + f
    open("/tmp/parse/" + f, "w").write(open(src).read())

import autopsy  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

SHARD = "/Users/jeronimoluza/.claude/jobs/f8501cf5/tmp/miss_shard0.jsonl.gz"

per_source = collections.defaultdict(lambda: collections.Counter())
names = collections.defaultdict(list)
n = 0
for line in gzip.open(SHARD, "rt", encoding="utf-8"):
    try:
        rec = json.loads(line)
    except Exception:
        continue
    n += 1
    soup = BeautifulSoup(rec["html"], "html.parser")
    try:
        row = autopsy.microdata_row(soup, rec["u"])
    except Exception:
        row = None
    if not row:
        continue
    s = rec["s"]
    c = per_source[s]
    c["converted"] += 1
    nm = row.get("product_name")
    if not nm:
        c["no_name"] += 1
        # would namefill rescue it, and with what?
        alt, src = autopsy.name_from_page(soup)
        if alt:
            c["namefill_" + src] += 1
            names[s].append(("FILL/" + src, alt, row["price"]))
    else:
        c["has_name"] += 1
        names[s].append(("MD", nm, row["price"]))

print("miss pages in shard: {:,}".format(n))
print()
print("%-22s %10s %9s %8s" % ("source", "converted", "has_name", "no_name"))
for s, c in sorted(per_source.items(), key=lambda x: -x[1]["converted"])[:14]:
    print("%-22s %10d %9d %8d" % (s, c["converted"], c["has_name"], c["no_name"]))

print()
print("SAMPLE NAMES for the two biggest contributors")
for s in ("ebay_uk", "otto_de", "hepsiburada_tr", "gamma_nl"):
    if s not in names:
        continue
    print("\n--- %s ---" % s)
    seen = set()
    for kind, nm, price in names[s][:400]:
        if nm in seen:
            continue
        seen.add(nm)
        print("  %-9s %-52s %s" % (kind, nm[:52], price))
        if len(seen) >= 8:
            break

print()
print("DISTINCT-NAME RATIO (a low ratio means the name is a category, not a product)")
print("%-22s %8s %8s %7s" % ("source", "rows", "distinct", "ratio"))
for s, c in sorted(per_source.items(), key=lambda x: -x[1]["converted"])[:14]:
    got = [nm for kind, nm, _ in names[s] if kind == "MD"]
    if not got:
        continue
    print("%-22s %8d %8d %6.2f" % (s, len(got), len(set(got)),
                                   len(set(got)) / len(got)))

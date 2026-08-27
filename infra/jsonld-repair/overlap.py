"""Do the microdata tier and the JSON-LD repair recover the same pages?

Their row counts can only be added if they convert disjoint misses. Both are
run over the identical archived miss corpus here so the intersection is
measured rather than assumed.
"""
import collections
import glob
import gzip
import json
import os
import sys

sys.path.insert(0, "/tmp/parse")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/Users/jeronimoluza/wb/pacificobservatory/repo/"
                   "pacific-observatory/.claude/worktrees/cc-infra-stage0/"
                   "infra/parse-probe")

import ldprobe as L  # noqa: E402
from ldrepair import parse_ld  # noqa: E402
from archived import rows_from_jsonld  # noqa: E402
import autopsy  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

SHARDS = sorted(glob.glob(
    "/Users/jeronimoluza/.claude/jobs/f8501cf5/tmp/miss_html/*.jsonl.gz"))


def ld_converts(html_text, url):
    blobs = L.ld_blobs(html_text)
    if not blobs:
        return False
    try:
        if rows_from_jsonld(html_text, url):
            return False
    except Exception:
        pass
    for raw, _s in blobs:
        for d in parse_ld(raw)[0]:
            for node in L.walk_deep(d):
                if not L.is_product(node, L.WIDE_PRODUCT):
                    continue
                price = None
                for off in L.offers_of(node):
                    price = (L.positive(L.price_shipped(off))
                             or L.positive(L.price_wide(off)))
                    if price:
                        break
                if not price:
                    price = L.positive(L.price_wide(node))
                if price and (L.node_name(node) or L.page_name(html_text)):
                    return True
    return False


cell = collections.Counter()
by_src = collections.defaultdict(collections.Counter)
n = 0
for path in SHARDS:
    for line in gzip.open(path, "rt", encoding="utf-8"):
        try:
            rec = json.loads(line)
        except Exception:
            continue
        n += 1
        html_text = rec.get("html") or ""
        url, src = rec.get("u", ""), rec.get("s", "?")
        ld = ld_converts(html_text, url)
        try:
            md = bool(autopsy.microdata_row(
                BeautifulSoup(html_text, "html.parser"), url))
        except Exception:
            md = False
        key = ("md" if md else "-") + "/" + ("ld" if ld else "-")
        cell[key] += 1
        by_src[src][key] += 1

print("archived miss pages: %d" % n)
print()
print("%-10s %8s  %s" % ("cell", "pages", "meaning"))
print("%-10s %8d  %s" % ("md/ld", cell["md/ld"], "both tiers recover it"))
print("%-10s %8d  %s" % ("md/-", cell["md/-"], "microdata only"))
print("%-10s %8d  %s" % ("-/ld", cell["-/ld"], "json-ld repair only"))
print("%-10s %8d  %s" % ("-/-", cell["-/-"], "neither"))
both = cell["md/ld"]
union = cell["md/ld"] + cell["md/-"] + cell["-/ld"]
print()
print("microdata total %d, json-ld total %d, union %d, overlap %d (%.1f%% of "
      "the json-ld set)" % (cell["md/ld"] + cell["md/-"],
                            cell["md/ld"] + cell["-/ld"], union, both,
                            100 * both / max(1, both + cell["-/ld"])))
print()
print("%-22s %7s %7s %7s %7s" % ("source", "both", "md only", "ld only",
                                 "neither"))
tot = collections.Counter({s: c["md/ld"] + c["-/ld"] for s, c in by_src.items()})
for s, _v in tot.most_common(10):
    c = by_src[s]
    print("%-22s %7d %7d %7d %7d" % (s, c["md/ld"], c["md/-"], c["-/ld"],
                                     c["-/-"]))

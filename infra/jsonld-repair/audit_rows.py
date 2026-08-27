"""Are the recovered rows real products, or template stubs?

The microdata tier taught this lesson: a conversion whose product_name is a
breadcrumb category or a JS variable is not a usable row. The yahoo_shopping_tw
sample here carried `"name":"Yahoo購物中心"` - the site's own name - with an
empty url and a ",,," description, which is a stub, not a product.
"""
import collections
import glob
import gzip
import json
import os
import sys

sys.path.insert(0, "/tmp/parse")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ldprobe as L  # noqa: E402
from ldrepair import parse_ld  # noqa: E402
from archived import rows_from_jsonld  # noqa: E402

SHARDS = sorted(glob.glob(
    "/Users/jeronimoluza/.claude/jobs/f8501cf5/tmp/miss_html/*.jsonl.gz"))

rows = []
for path in SHARDS:
    for line in gzip.open(path, "rt", encoding="utf-8"):
        try:
            rec = json.loads(line)
        except Exception:
            continue
        html_text = rec.get("html") or ""
        blobs = L.ld_blobs(html_text)
        if not blobs:
            continue
        try:
            if rows_from_jsonld(html_text, rec.get("u", "")):
                continue
        except Exception:
            pass
        vals = []
        for raw, _s in blobs:
            v, _how = parse_ld(raw)
            vals.extend(v)
        for d in vals:
            hit = None
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
                if not price:
                    continue
                name = L.node_name(node) or L.page_name(html_text)
                if not name:
                    continue
                hit = {"s": rec.get("s"), "c": rec.get("c"),
                       "u": rec.get("u", ""), "name": name, "price": price,
                       "node_url": node.get("url") or "",
                       "sku": node.get("sku") or node.get("productID") or "",
                       "desc": str(node.get("description") or "")[:40],
                       "type": ",".join(L.type_of(node))}
                break
            if hit:
                rows.append(hit)
                break

print("recovered rows: %d" % len(rows))
per = collections.Counter(r["s"] for r in rows)
print("\n%-24s %6s %8s %7s   %s" % ("source", "rows", "distinct", "ratio",
                                    "verdict"))
suspect = {}
for s, n in per.most_common(20):
    got = [r["name"] for r in rows if r["s"] == s]
    d = len(set(got))
    ratio = d / n
    top, topn = collections.Counter(got).most_common(1)[0]
    dominant = topn / n
    v = "OK"
    if ratio < 0.5 or dominant > 0.4:
        v = "STUB? '%s' x%d" % (top[:24], topn)
    suspect[s] = v
    print("%-24s %6d %8d %6.2f   %s" % (s, n, d, ratio, v))

print("\n=== SAMPLE ROWS (name | price | sku | node url present) ===")
seen = set()
for r in rows:
    k = r["s"]
    if k in seen:
        continue
    seen.add(k)
    print("[%-20s] %-42s %-12s sku=%-10s url=%s" % (
        k, r["name"][:42], r["price"], str(r["sku"])[:10],
        "yes" if r["node_url"] else "NO"))
    if len(seen) >= 16:
        break

print("\n=== PRICE SANITY ===")
vals = [float(r["price"]) for r in rows]
vals.sort()
print("min %.2f  p25 %.2f  median %.2f  p75 %.2f  max %.2f" % (
    vals[0], vals[len(vals) // 4], vals[len(vals) // 2],
    vals[3 * len(vals) // 4], vals[-1]))
print("price == 1.0 : %d" % sum(1 for v in vals if v == 1.0))
print("price < 0.01 : %d" % sum(1 for v in vals if v < 0.01))

json.dump(rows, open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "recovered_rows.json"), "w"),
          ensure_ascii=False, indent=1)

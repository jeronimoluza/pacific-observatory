"""Attribute every JSON-LD-present-but-unparsed miss, and price the fixes.

Reads the archived miss HTML, keeps pages carrying an `application/ld+json`
script, confirms the shipped extractor really produces nothing, then walks a
ladder of candidate widenings measuring how many pages each converts into a
usable (name + positive price) row.
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

stat = collections.Counter()
types_deep = collections.Counter()
how_counts = collections.Counter()
block = collections.Counter()
ladder = collections.Counter()
marginal = collections.Counter()
by_source = collections.defaultdict(collections.Counter)
by_crawl = collections.defaultdict(collections.Counter)
examples = collections.defaultdict(list)

# (label, accepted types, price-off-node, name-fallback, use repaired parse)
RUNGS = [
    ("L0_shipped", L.SHIPPED_PRODUCT, False, False, False),
    ("L1_deepwalk", L.SHIPPED_PRODUCT, False, False, False),
    ("L2_widetypes", L.WIDE_PRODUCT, False, False, False),
    ("L3_nodeprice", L.WIDE_PRODUCT, True, False, False),
    ("L4_namefill", L.WIDE_PRODUCT, True, True, False),
    ("L5_jsonrepair", L.WIDE_PRODUCT, True, True, True),
]


def usable(node, html_text, types, deep_price, name_fb):
    """(name, price) if this node yields a usable row under the given rules."""
    if not L.is_product(node, types):
        return None
    price = None
    for off in L.offers_of(node):
        price = L.positive(L.price_shipped(off))
        if not price and deep_price:
            price = L.positive(L.price_wide(off))
        if price:
            break
    if not price and deep_price:
        price = L.positive(L.price_wide(node))
    if not price:
        return None
    name = L.node_name(node)
    if not name and name_fb:
        name = L.page_name(html_text)
    if not name:
        return None
    return name, price


for path in SHARDS:
    for line in gzip.open(path, "rt", encoding="utf-8"):
        try:
            rec = json.loads(line)
        except Exception:
            stat["bad_line"] += 1
            continue
        stat["miss_pages"] += 1
        html_text = rec.get("html") or ""
        src, crawl = rec.get("s", "?"), rec.get("c", "?")
        by_source[src]["archived_miss"] += 1

        blobs = L.ld_blobs(html_text)
        if not blobs:
            stat["no_ld_script"] += 1
            continue
        stat["has_ld_script"] += 1

        try:
            if rows_from_jsonld(html_text, rec.get("u", "")):
                stat["shipped_would_hit"] += 1
                continue
        except Exception:
            stat["shipped_raised"] += 1

        stat["confirmed_ld_miss"] += 1
        by_source[src]["ld_miss"] += 1
        by_crawl[crawl]["ld_miss"] += 1

        # ---- two parses of the same blobs: shipped-strict, and repaired
        strict_vals, rep_vals = [], []
        for raw, _s in blobs:
            try:
                strict_vals.append(json.loads(raw))
            except Exception:
                pass
            vals, how = parse_ld(raw)
            how_counts[how] += 1
            rep_vals.extend(vals)
        if not strict_vals and rep_vals:
            stat["rescued_by_repair"] += 1
        if not rep_vals:
            stat["unparseable_even_repaired"] += 1

        nodes_shipped = [n for d in strict_vals for n in L.walk_shipped(d)]
        nodes_deep = [n for d in strict_vals for n in L.walk_deep(d)]
        nodes_rep = [n for d in rep_vals for n in L.walk_deep(d)]
        seen_t = set()
        for n in nodes_rep:
            for t in L.type_of(n):
                if t not in seen_t:
                    types_deep[t] += 1
                    seen_t.add(t)

        # ---- first blocking reason under the shipped rules
        prod_shipped = [n for n in nodes_shipped
                        if L.is_product(n, L.SHIPPED_PRODUCT)]
        prod_deep = [n for n in nodes_deep if L.is_product(n, L.SHIPPED_PRODUCT)]
        prod_wide = [n for n in nodes_deep if L.is_product(n, L.WIDE_PRODUCT)]
        prod_rep = [n for n in nodes_rep if L.is_product(n, L.WIDE_PRODUCT)]

        if not strict_vals:
            block["json_would_not_parse" if not rep_vals
                  else "json_malformed_repairable"] += 1
        elif not prod_shipped and prod_deep:
            block["product_nested_below_graph"] += 1
        elif not prod_wide and prod_rep:
            block["product_only_in_repaired_blob"] += 1
        elif not prod_wide:
            block["no_product_node_at_all"] += 1
            if len(examples["notype"]) < 10:
                examples["notype"].append(
                    (src, sorted({t for n in nodes_deep
                                  for t in L.type_of(n)})[:8]))
        elif not prod_deep:
            block["product_type_not_accepted"] += 1
            if len(examples["othertype"]) < 10:
                examples["othertype"].append(
                    (src, sorted({t for n in prod_wide
                                  for t in L.type_of(n)})[:5]))
        else:
            has_off = any(L.offers_of(n) for n in prod_wide)
            has_np = any(L.price_wide(n) for n in prod_wide)
            has_nm = any(L.node_name(n) for n in prod_wide)
            if not has_off and has_np:
                block["price_on_node_not_in_offers"] += 1
            elif not has_off:
                block["product_has_no_offers_and_no_price"] += 1
            elif not has_nm:
                block["product_has_no_name"] += 1
            else:
                block["offers_present_but_price_unusable"] += 1

        # ---- ladder
        prev = False
        for label, types, dp, nf, use_rep in RUNGS:
            nodes = (nodes_rep if use_rep
                     else (nodes_shipped if label == "L0_shipped"
                           else nodes_deep))
            hit = None
            for node in nodes:
                got = usable(node, html_text, types, dp, nf)
                if got:
                    hit = (node, got)
                    break
            if hit:
                ladder[label] += 1
                if not prev:
                    marginal[label] += 1
                    by_source[src]["conv"] += 1
                    by_crawl[crawl]["conv"] += 1
                    if len(examples[label]) < 6:
                        node, (nm, pr) = hit
                        examples[label].append(
                            (src, L.type_of(node), nm[:60], pr))
                prev = True

out = {
    "stat": dict(stat), "block": dict(block), "ladder": dict(ladder),
    "marginal": dict(marginal), "parse_how": dict(how_counts),
    "types_deep": dict(types_deep.most_common(40)),
    "by_source": {k: dict(v) for k, v in by_source.items()},
    "by_crawl": {k: dict(v) for k, v in by_crawl.items()},
    "examples": {k: v for k, v in examples.items()},
    "shards": len(SHARDS),
}
dest = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "ldx_result.json")
with open(dest, "w") as fh:
    json.dump(out, fh, indent=1, ensure_ascii=False, default=str)

n = stat["confirmed_ld_miss"]
print("shards %d   miss pages %d   with ld+json %d   confirmed ld miss %d"
      % (len(SHARDS), stat["miss_pages"], stat["has_ld_script"], n))
print()
print("%-38s %7s %7s" % ("BLOCKING REASON", "pages", "share"))
for k, v in sorted(block.items(), key=lambda x: -x[1]):
    print("%-38s %7d %6.1f%%" % (k, v, 100 * v / n))
print()
print("%-20s %8s %9s %8s" % ("LADDER (cumulative)", "conv", "of misses", "new"))
for label, _t, _d, _nf, _r in RUNGS:
    print("%-20s %8d %8.1f%% %8d"
          % (label, ladder[label], 100 * ladder[label] / n, marginal[label]))
print()
print("parse stages:", dict(how_counts.most_common(8)))
print("wrote", dest)

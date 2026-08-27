"""Which currencies write a lone dot as a THOUSANDS separator?

`normalize_price` has branches for comma+dot and for a lone comma, but none
for a lone dot, so a lone dot always reaches float() as a decimal point and
`78.000` VND silently becomes 78.0.

Fixing that needs to know which currencies mean thousands by a lone dot. That
is a locale convention, so it is measured here off real archived storefront
markup rather than assumed: every (price string, currency) pair in the miss
corpus is bucketed by the SHAPE of the price string, grouped by currency.

The tell is unambiguous in aggregate. A currency that quotes minor units puts
exactly 2 digits after its decimal mark; one that does not will show a mass of
3-digit tails and essentially no 2-digit tails.
"""
import collections
import glob
import gzip
import json
import re
import sys

SHARDS = sorted(glob.glob(
    "/Users/jeronimoluza/.claude/jobs/f8501cf5/tmp/miss_html/*.jsonl.gz"))

# price/currency pairs as they appear in schema.org markup, both the JSON-LD
# form ("price": "78.000", "priceCurrency": "VND") and the microdata form
# (<meta itemprop="price" content="78.000">).
_JSON_PRICE = re.compile(
    r'"(?:price|lowPrice|highPrice)"\s*:\s*"?([\d.,]+)"?', re.I)
_JSON_CUR = re.compile(r'"priceCurrency"\s*:\s*"([A-Za-z]{3})"')
_META_PRICE = re.compile(
    r'itemprop=["\'](?:price|lowPrice)["\'][^>]*content=["\']([\d.,]+)["\']', re.I)
_META_PRICE2 = re.compile(
    r'content=["\']([\d.,]+)["\'][^>]*itemprop=["\'](?:price|lowPrice)["\']', re.I)
_META_CUR = re.compile(
    r'itemprop=["\']priceCurrency["\'][^>]*content=["\']([A-Za-z]{3})["\']', re.I)
_OG_PRICE = re.compile(
    r'(?:product:price:amount|og:price:amount)["\'][^>]*content=["\']([\d.,]+)["\']', re.I)
_OG_CUR = re.compile(
    r'(?:product:price:currency|og:price:currency)["\'][^>]*content=["\']([A-Za-z]{3})["\']', re.I)


def shape(s):
    """Bucket a raw price string by its separator layout."""
    has_c, has_d = "," in s, "." in s
    if has_c and has_d:
        return "both"
    if has_c:
        n = len(s.split(",")[-1])
        return "comma_tail%d" % n if n <= 3 else "comma_tailN"
    if has_d:
        if s.count(".") > 1:
            return "multidot"
        n = len(s.split(".")[-1])
        return "dot_tail%d" % n if n <= 3 else "dot_tailN"
    return "plain"


by_cur = collections.defaultdict(collections.Counter)
examples = collections.defaultdict(list)
pages = 0

for path in SHARDS:
    for line in gzip.open(path, "rt", encoding="utf-8"):
        try:
            rec = json.loads(line)
        except Exception:
            continue
        html = rec.get("html") or ""
        if not html:
            continue
        pages += 1
        # one currency per page is the overwhelming norm; take the first seen
        cur = None
        for rx in (_JSON_CUR, _META_CUR, _OG_CUR):
            m = rx.search(html)
            if m:
                cur = m.group(1).upper()
                break
        if not cur:
            continue
        prices = []
        for rx in (_JSON_PRICE, _META_PRICE, _META_PRICE2, _OG_PRICE):
            prices.extend(rx.findall(html))
        for p in prices[:40]:
            if not p or not any(ch.isdigit() for ch in p):
                continue
            sh = shape(p)
            by_cur[cur][sh] += 1
            if sh in ("dot_tail3", "dot_tail2") and len(examples[(cur, sh)]) < 4:
                examples[(cur, sh)].append(p)

print("pages scanned with a currency: %d" % pages)
print()
hdr = ("currency", "n", "dot_t3", "dot_t2", "dot_t1", "multidot", "comma_t2",
       "comma_t3", "plain")
print("%-4s %8s %8s %8s %7s %9s %9s %9s %8s   verdict" % hdr)

ZERO_HINT = []
for cur, c in sorted(by_cur.items(), key=lambda kv: -sum(kv[1].values())):
    n = sum(c.values())
    if n < 25:
        continue
    d3, d2, d1 = c["dot_tail3"], c["dot_tail2"], c["dot_tail1"]
    # A minor-unit currency shows 2-digit tails. One that writes dot-thousands
    # shows 3-digit tails and almost no 2-digit ones.
    verdict = ""
    if d3 >= 10 and d3 > 4 * (d2 + d1):
        verdict = "DOT=THOUSANDS"
        ZERO_HINT.append(cur)
    elif d2 > 0 and d2 >= d3:
        verdict = "dot=decimal"
    print("%-4s %8d %8d %8d %7d %9d %9d %9d %8d   %s" % (
        cur, n, d3, d2, d1, c["multidot"], c["comma_tail2"], c["comma_tail3"],
        c["plain"], verdict))

print()
print("currencies whose lone dot is a THOUSANDS separator (measured):")
print("  " + " ".join(sorted(ZERO_HINT)))
print()
for (cur, sh), ex in sorted(examples.items()):
    if sh == "dot_tail3" and cur in ZERO_HINT:
        print("  %-4s %s" % (cur, ", ".join(ex)))

"""Does the dot-thousands pattern appear in VISIBLE price text?

survey.py found zero 3-digit dot tails in structured markup: schema.org wants a
machine-readable number, so JSON-LD and microdata carry `78000`. That means the
`78.000 -> 78.0` defect cannot bite the JSON-LD tier at all, and the claim that
it "affects every tier" needs re-testing against the surface that actually
carries locale-formatted numbers - the rendered price text a CSS selector reads.

So: find numbers adjacent to a currency symbol or code in the page text, and
bucket them by separator shape, keyed on the page's declared currency.
"""
import collections
import glob
import gzip
import html as _html
import json
import re

SHARDS = sorted(glob.glob(
    "/Users/jeronimoluza/.claude/jobs/f8501cf5/tmp/miss_html/*.jsonl.gz"))

_CUR = re.compile(r'"priceCurrency"\s*:\s*"([A-Za-z]{3})"')
_TAG = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
_STRIP = re.compile(r"<[^>]+>")

# a number sitting next to a currency marker, either side
_SYM = r"(?:[$€£¥₫₩₹₪₺₦₱₽฿﷼]|Rp|R\$|RM|NT\$|HK\$|S\$|zł|Kč|Ft|лв|грн|so'm|so‘m|"
_SYM += r"USD|EUR|GBP|VND|IDR|CLP|COP|JPY|KRW|TRY|BRL|MXN|ARS|PYG|ISK|HUF|PKR|IRR|MYR|TWD|THB|PHP)"
_NUM = r"(\d{1,3}(?:[.,\s]\d{3})+(?:[.,]\d{1,3})?|\d+(?:[.,]\d{1,3})?)"
_PRICE_TEXT = re.compile(_SYM + r"\s*" + _NUM + r"|" + _NUM + r"\s*" + _SYM)


def shape(s):
    s = s.replace(" ", "").replace(" ", "")
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

for path in SHARDS:
    for line in gzip.open(path, "rt", encoding="utf-8"):
        try:
            rec = json.loads(line)
        except Exception:
            continue
        raw = rec.get("html") or ""
        if not raw:
            continue
        m = _CUR.search(raw)
        cur = m.group(1).upper() if m else None
        if not cur:
            continue
        text = _html.unescape(_STRIP.sub(" ", _TAG.sub(" ", raw)))
        hits = 0
        for mt in _PRICE_TEXT.finditer(text):
            num = mt.group(1) or mt.group(2)
            if not num:
                continue
            sh = shape(num)
            by_cur[cur][sh] += 1
            if sh == "dot_tail3" and len(examples[cur]) < 5:
                examples[cur].append(num)
            hits += 1
            if hits >= 30:
                break

print("%-4s %8s %9s %9s %9s %9s %9s %8s   verdict" % (
    "cur", "n", "dot_t3", "dot_t2", "dot_t1", "comma_t3", "comma_t2", "plain"))
flagged = []
for cur, c in sorted(by_cur.items(), key=lambda kv: -sum(kv[1].values())):
    n = sum(c.values())
    if n < 40:
        continue
    d3, d2, d1 = c["dot_tail3"], c["dot_tail2"], c["dot_tail1"]
    verdict = ""
    if d3 >= 10 and d3 > 3 * (d2 + d1):
        verdict = "DOT=THOUSANDS"
        flagged.append(cur)
    elif d3 >= 10:
        verdict = "ambiguous (both shapes present)"
    print("%-4s %8d %9d %9d %9d %9d %9d %8d   %s" % (
        cur, n, d3, d2, d1, c["comma_tail3"], c["comma_tail2"], c["plain"],
        verdict))

print()
print("dot=thousands currencies (measured in visible text): %s" %
      (" ".join(sorted(flagged)) or "NONE"))
for cur in sorted(flagged):
    print("  %-4s %s" % (cur, ", ".join(examples[cur])))

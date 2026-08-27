"""Can the au_pay_market mojibake be undone from what was archived?

The repair rescued 91 au_pay_market rows whose names are mojibake. Both the
stray backslash and the garbled name have one cause: Shift_JIS bytes read as
a single-byte encoding. If the archived text preserved those bytes, decoding
them properly fixes the name AND removes the need for the escape repair.
Also confirms yahoo_shopping_tw's template stub never became a row.
"""
import glob
import gzip
import json
import os
import re
import sys

sys.path.insert(0, "/tmp/parse")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ldprobe as L  # noqa: E402
from ldrepair import parse_ld  # noqa: E402

SHARDS = sorted(glob.glob(
    "/Users/jeronimoluza/.claude/jobs/f8501cf5/tmp/miss_html/*.jsonl.gz"))
CHARSET = re.compile(
    r'charset["\']?\s*[=:]\s*["\']?\s*([\w\-]+)', re.IGNORECASE)

shown = 0
recover_ok = recover_fail = 0
yahoo_seen = yahoo_rows = 0
for path in SHARDS:
    for line in gzip.open(path, "rt", encoding="utf-8"):
        try:
            rec = json.loads(line)
        except Exception:
            continue
        src = rec.get("s")
        html_text = rec.get("html") or ""
        if src == "yahoo_shopping_tw":
            yahoo_seen += 1
            for raw, _s in L.ld_blobs(html_text):
                for d in parse_ld(raw)[0]:
                    for node in L.walk_deep(d):
                        if L.is_product(node, L.WIDE_PRODUCT):
                            p = None
                            for off in L.offers_of(node):
                                p = L.positive(L.price_shipped(off))
                                if p:
                                    break
                            if p:
                                yahoo_rows += 1
        if src != "au_pay_market":
            continue
        m = CHARSET.search(html_text[:4000])
        declared = (m.group(1).lower() if m else None)
        # the archived text kept the original bytes if it round-trips latin-1
        try:
            raw_bytes = html_text.encode("latin-1")
        except UnicodeEncodeError:
            recover_fail += 1
            continue
        try:
            fixed = raw_bytes.decode("cp932")
        except UnicodeDecodeError:
            fixed = raw_bytes.decode("cp932", errors="replace")
        blobs_fixed = L.ld_blobs(fixed)
        if not blobs_fixed:
            continue
        vals, how = parse_ld(blobs_fixed[0][0])
        name = None
        for d in vals:
            for node in L.walk_deep(d):
                if L.is_product(node, L.WIDE_PRODUCT):
                    name = L.node_name(node)
                    break
            if name:
                break
        if name and not any(ch in name for ch in "�"):
            recover_ok += 1
        else:
            recover_fail += 1
        if shown < 6 and name:
            print("declared=%-10s stage=%-9s name=%s" % (declared, how, name[:56]))
            shown += 1

print()
print("au_pay_market pages whose name decodes cleanly as cp932: %d" % recover_ok)
print("au_pay_market pages still broken:                        %d" % recover_fail)
print()
print("yahoo_shopping_tw miss pages: %d, of which produced a priced row: %d"
      % (yahoo_seen, yahoo_rows))

"""Exact cause of every JSON-LD parse failure, with the offending context.

The ladder found 104 blobs that will not parse even after repair, and the
samples were all real Product nodes. A generic "unparseable" bucket is not
actionable; the json.JSONDecodeError message and the characters either side
of its reported position are.
"""
import collections
import glob
import gzip
import json
import os
import re
import sys

sys.path.insert(0, "/tmp/parse")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ldprobe as L  # noqa: E402

SHARDS = sorted(glob.glob(
    "/Users/jeronimoluza/.claude/jobs/f8501cf5/tmp/miss_html/*.jsonl.gz"))
if not SHARDS:
    SHARDS = ["/Users/jeronimoluza/.claude/jobs/f8501cf5/tmp/miss_shard0.jsonl.gz"]

cause = collections.Counter()
by_src = collections.defaultdict(collections.Counter)
snips = collections.defaultdict(list)
has_product_text = collections.Counter()
truncated = collections.Counter()


def classify(raw, err):
    """Map a JSONDecodeError onto a repairable cause."""
    msg = err.msg if hasattr(err, "msg") else str(err)
    pos = getattr(err, "pos", 0) or 0
    ctx = raw[max(0, pos - 60):pos + 60]
    if "Expecting value" in msg and re.search(r":\s*undefined", ctx):
        return "js_undefined_literal", ctx
    if "Expecting value" in msg and re.search(r":\s*NaN|:\s*Infinity", ctx):
        return "js_nan_infinity", ctx
    if "Unterminated string" in msg or "Expecting ',' delimiter" in msg:
        if pos > len(raw) - 200:
            return "truncated_blob", ctx
        return "unescaped_quote_or_delim", ctx
    if "Invalid control character" in msg:
        return "raw_control_char", ctx
    if "Expecting ',' delimiter" in msg:
        return "delimiter", ctx
    if "Extra data" in msg:
        return "extra_data_after_json", ctx
    if "Expecting property name" in msg:
        return "trailing_comma_or_key", ctx
    if "Invalid \\escape" in msg:
        return "invalid_backslash_escape", ctx
    if "Expecting value" in msg and pos >= len(raw.rstrip()) - 2:
        return "truncated_blob", ctx
    return "other:" + msg[:40], ctx


n_pages = 0
for path in SHARDS:
    for line in gzip.open(path, "rt", encoding="utf-8"):
        try:
            rec = json.loads(line)
        except Exception:
            continue
        html_text = rec.get("html") or ""
        src = rec.get("s", "?")
        for raw, _s in L.ld_blobs(html_text):
            d, how = L.parse_any(raw)
            if d is not None:
                continue
            n_pages += 1
            # what did the strict parse actually complain about?
            try:
                json.loads(L.repair(raw))
                continue
            except json.JSONDecodeError as e:
                c, ctx = classify(L.repair(raw), e)
            except Exception as e:  # noqa: BLE001
                c, ctx = "nonjson:" + type(e).__name__, ""
            cause[c] += 1
            by_src[src][c] += 1
            if '"@type"' in raw and "roduct" in raw:
                has_product_text[c] += 1
            if not raw.rstrip().endswith(("}", "]")):
                truncated[c] += 1
            if len(snips[c]) < 4:
                snips[c].append((src, ctx.replace("\n", " ")[:150]))

print("unparseable blobs: %d" % n_pages)
print()
print("%-32s %6s %9s %10s" % ("cause", "blobs", "look like", "unclosed"))
print("%-32s %6s %9s %10s" % ("", "", "products", "blob"))
for c, n in cause.most_common(20):
    print("%-32s %6d %9d %10d" % (c, n, has_product_text[c], truncated[c]))
print()
print("=== CONTEXT AROUND THE FAILURE ===")
for c, _n in cause.most_common(8):
    print("\n--- %s ---" % c)
    for s, ctx in snips[c]:
        print("  [%s] %s" % (s, ctx))
print()
print("=== TOP SOURCES ===")
tot = collections.Counter()
for s, cc in by_src.items():
    tot[s] = sum(cc.values())
for s, n in tot.most_common(12):
    print("%-24s %4d  %s" % (s, n, dict(by_src[s].most_common(3))))

json.dump({"cause": dict(cause), "product_text": dict(has_product_text),
           "truncated": dict(truncated),
           "by_src": {k: dict(v) for k, v in by_src.items()}},
          open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "unparseable.json"), "w"), indent=1)

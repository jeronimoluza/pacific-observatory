"""Offline checks for the fetch driver's record path -- no network, no creds.

Everything between "bytes came back from S3" and "a row is written" is pure,
so it can be tested against the archived miss corpus by wrapping real captured
HTML back into the WARC envelope it came out of.

The timestamp assertion is the one that matters most. `scraped_at_utc` must
carry the *capture* time; stamping `now()` collapses a decade of observations
onto today, which is the failure this whole exercise exists to avoid and which
no downstream check would catch.
"""
import glob
import gzip
import json
import os
import sys

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("PARSE_DIR", "/tmp/parsebundle")

sys.path.insert(
    0,
    "/Users/jeronimoluza/wb/pacificobservatory/repo/pacific-observatory/"
    ".claude/worktrees/cc-infra-stage0/infra/fetch",
)
import ccfetch  # noqa: E402

SHARDS = sorted(glob.glob(
    "/Users/jeronimoluza/.claude/jobs/f8501cf5/tmp/miss_html/*.jsonl.gz"))


def warc(html_bytes, charset=None):
    """Rebuild the on-disk shape: gzipped WARC envelope, HTTP headers, body."""
    ct = "text/html" + ("; charset=%s" % charset if charset else "")
    blob = (
        b"WARC/1.0\r\nWARC-Type: response\r\n\r\n"
        b"HTTP/1.1 200 OK\r\nContent-Type: " + ct.encode() + b"\r\n\r\n"
        + html_bytes
    )
    return gzip.compress(blob)


FAILED = []


def check(name, cond, detail=""):
    if not cond:
        FAILED.append(name)
        print("FAIL  %s  %s" % (name, detail))


def main():
    # --- envelope -------------------------------------------------------
    hdrs, body = ccfetch.split_warc(warc(b"<html>hi</html>"))
    check("split_warc returns headers and body",
          hdrs is not None and body == b"<html>hi</html>", repr(body))

    bad, reason = ccfetch.split_warc(b"not gzip at all")
    check("non-gzip is reported, not raised",
          bad is None and reason == "gunzip_failed", reason)

    # --- charset --------------------------------------------------------
    sjis = "商品名".encode("shift_jis")
    hdrs, body = ccfetch.split_warc(warc(sjis, charset="shift_jis"))
    check("declared charset beats latin-1",
          ccfetch.decode(hdrs, body) == "商品名",
          repr(ccfetch.decode(hdrs, body)))

    hdrs, body = ccfetch.split_warc(warc("café".encode("utf-8")))
    check("utf-8 default still works",
          ccfetch.decode(hdrs, body) == "café")

    hdrs, body = ccfetch.split_warc(warc(b"\xff\xfe bad", charset="nosuchenc"))
    check("unknown charset falls back instead of raising",
          isinstance(ccfetch.decode(hdrs, body), str))

    # --- timestamp ------------------------------------------------------
    check("capture stamp is parsed as UTC",
          ccfetch.to_iso("20170314092233") == "2017-03-14T09:22:33+00:00",
          ccfetch.to_iso("20170314092233"))
    check("a junk stamp is None, never now()", ccfetch.to_iso("nonsense") is None)

    # --- the ladder on real archived pages -------------------------------
    seen = tiers = 0
    counts = {}
    stamps_ok = True
    for path in SHARDS[:2]:
        for line in gzip.open(path, "rt", encoding="utf-8"):
            rec = json.loads(line)
            seen += 1
            rows, tier = ccfetch.parse_rows(rec["html"], rec["u"])
            counts[tier] = counts.get(tier, 0) + 1
            if rows:
                tiers += 1
            if seen >= 2500:
                break
        if seen >= 2500:
            break
    check("microdata fires on the real corpus",
          counts.get("microdata", 0) > 0, str(counts))
    print("  ladder over %d real pages: %s" % (seen, counts))

    # --- a full record, end to end ---------------------------------------
    html = (
        '<div itemscope itemtype="http://schema.org/Product">'
        '<span itemprop="name">Arroz Grado 1</span>'
        '<span itemprop="price">1.990</span>'
        '<meta itemprop="priceCurrency" content="CLP"></div>'
    )
    raw = warc(html.encode("utf-8"))
    hdrs, body = ccfetch.split_warc(raw)
    rows, tier = ccfetch.parse_rows(ccfetch.decode(hdrs, body),
                                    "http://tienda.cl/p/arroz")
    stamp = ccfetch.to_iso("20161122081500")
    check("end to end yields one row via microdata",
          len(rows) == 1 and tier == "microdata", "%s %s" % (tier, rows))
    if rows:
        check("dot-thousands resolved by currency",
              rows[0]["price"] == "1990.0", rows[0]["price"])
        check("stamp is the capture, not today",
              stamp.startswith("2016-11-22"), stamp)

    print("\n%d checks failed" % len(FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())

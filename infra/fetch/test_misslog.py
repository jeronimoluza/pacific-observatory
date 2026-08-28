"""Drive run_crawl end to end offline and check the miss log is complete.

A unit test on the parse tiers would not catch this: the thing that can break is
the bookkeeping around them -- a miss silently dropped, or a record counted
twice. So this stubs S3 and the manifest and runs the real run_crawl, then
asserts rows + misses accounts for every record.
"""
import glob
import gzip
import json
import os
import sys

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "dummy")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "dummy")
os.environ.setdefault("PARSE_DIR", "/Users/jeronimoluza/.claude/jobs/f8501cf5/tmp/parse")
os.environ["OUT_BUCKET"] = ""
os.environ["WORK"] = "/Users/jeronimoluza/.claude/jobs/f8501cf5/tmp/misswork"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ccfetch  # noqa: E402

GOOD = (
    '<div itemscope itemtype="http://schema.org/Product">'
    '<span itemprop="name">Arroz</span><span itemprop="price">1990</span>'
    '<meta itemprop="priceCurrency" content="CLP"></div>'
)
BARE = "<html><body>no product here</body></html>"

FAILED = []


def check(name, cond, detail=""):
    if not cond:
        FAILED.append(name)
        print("FAIL  %s  %s" % (name, detail))


def warc(html):
    blob = (b"WARC/1.0\r\nWARC-Type: response\r\n\r\n"
            b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n"
            + html.encode("utf-8"))
    return gzip.compress(blob)


class Body:
    def __init__(self, raw):
        self.raw = raw

    def read(self):
        return self.raw


class FakeS3:
    """Half the records parse, one is a hard S3 error, the rest are bare."""

    def get_object(self, Bucket, Key, Range=None):
        if Key == "boom":
            raise RuntimeError("simulated get failure")
        html = GOOD if Key.endswith("g") else BARE
        return {"Body": Body(warc(html))}

    def upload_file(self, *a, **k):
        raise AssertionError("must not upload when OUT_BUCKET is empty")

    def list_objects_v2(self, **k):
        return {}


N_GOOD, N_BARE = 40, 55
RECS = (
    [{"filename": "f%dg" % i, "offset": 0, "length": 10, "url": "http://x/%d" % i,
      "timestamp": "20170101000000", "spider": "src"} for i in range(N_GOOD)]
    + [{"filename": "f%db" % i, "offset": 0, "length": 10, "url": "http://y/%d" % i,
        "timestamp": "20170101000000", "spider": "src"} for i in range(N_BARE)]
    + [{"filename": "boom", "offset": 0, "length": 10, "url": "http://z/0",
        "timestamp": "20170101000000", "spider": "src"}]
)


def main():
    ccfetch._s3 = FakeS3()
    ccfetch.iter_manifest = lambda index: iter(RECS)
    work = os.environ["WORK"]
    for f in glob.glob(os.path.join(work, "*")):
        os.remove(f)

    rc = ccfetch.run_crawl("CC-TEST-0001")
    check("run_crawl returns 0", rc == 0, str(rc))

    rows = list(gzip.open(os.path.join(work, "CC-TEST-0001-00.jsonl.gz"), "rt"))
    miss = [json.loads(x) for x in
            gzip.open(os.path.join(work, "CC-TEST-0001-00.miss.jsonl.gz"), "rt")]

    check("every record is either a row or a miss",
          len(rows) + len(miss) == len(RECS),
          "rows=%d miss=%d recs=%d" % (len(rows), len(miss), len(RECS)))
    check("parsed count matches the good records", len(rows) == N_GOOD, len(rows))
    check("miss count matches bare plus failed",
          len(miss) == N_BARE + 1, len(miss))

    addressed = [m for m in miss if m["filename"] and m["offset"] is not None]
    check("every miss carries a re-fetchable WARC address",
          len(addressed) == len(miss),
          "%d of %d" % (len(addressed), len(miss)))

    reasons = {m["reason"] for m in miss}
    check("bare pages are logged as no_extract", "no_extract" in reasons, reasons)
    check("the S3 failure is logged with its own reason",
          any(r.startswith("get_failed") for r in reasons), reasons)
    check("miss rows keep the capture timestamp",
          all(m["timestamp"] == "20170101000000" for m in miss))

    print("\n%d checks failed" % len(FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())

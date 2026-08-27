"""Pre-flight for autopsy.py: exercise the new tiers before paying for EC2.

Runs against hand-built markup in the eras we care about, so a bug in the
microdata/RDFa/charset paths surfaces here rather than after a 40-minute run
whose only output is a wrong number.

Usage:  python bundle.py /tmp/parse && python test_autopsy.py
"""
import gzip
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

STAGE = os.environ.get("PARSE_STAGE", "/tmp/parse")
sys.path.insert(0, STAGE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import autopsy  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

FAILED = []


def check(name, got, want):
    ok = got == want
    print("%-46s %s   got=%r" % (name, "PASS" if ok else "FAIL", got))
    if not ok:
        FAILED.append((name, got, want))


def soup(h):
    return BeautifulSoup(h, "html.parser")


# ---- inline microdata, the 2011-2016 shape the meta tier cannot see ----
MD = """<html><body>
<div itemscope itemtype="http://schema.org/Product">
  <h1 itemprop="name">Arroz Integral 1kg</h1>
  <div itemprop="offers" itemscope itemtype="http://schema.org/Offer">
    <span itemprop="price">12.50</span>
    <meta itemprop="priceCurrency" content="EUR"/>
  </div>
</div></body></html>"""
r = autopsy.microdata_row(soup(MD), "http://x.com/p")
check("microdata price", r and r["price"], "12.5")
check("microdata name", r and r["product_name"], "Arroz Integral 1kg")
check("microdata currency", r and r["currency"], "EUR")

MD2 = """<div itemscope itemtype="https://schema.org/Product">
<span itemprop="name">Leche</span>
<span itemprop="price" content="3.99">R$ 3,99</span></div>"""
check("microdata content-attr price",
      autopsy.microdata_row(soup(MD2), "u")["price"], "3.99")

# price present, name absent: namefill is what must rescue this row
MD3 = """<html><head><meta property="og:title" content="Sugar 2kg"></head>
<body><div itemscope itemtype="http://schema.org/Product">
<span itemprop="price">8.00</span></div></body></html>"""
s3 = soup(MD3)
r = autopsy.microdata_row(s3, "u")
check("microdata no-name price", r and r["price"], "8.0")
check("microdata no-name name is None", r and r["product_name"], None)
check("namefill from og:title", autopsy.name_from_page(s3), ("Sugar 2kg", "og:title"))

MD4 = """<div itemscope itemtype="http://schema.org/Product">
<span itemprop="name">X</span><span itemprop="price">0</span></div>"""
check("microdata zero price rejected", autopsy.microdata_row(soup(MD4), "u"), None)
check("microdata absent -> None",
      autopsy.microdata_row(soup("<html><body><p>hi</p></body></html>"), "u"), None)

# ---- RDFa ----
RD = """<div vocab="http://schema.org/" typeof="Product">
<span property="name">Cafe 500g</span>
<span property="price" content="15.00">15,00</span>
<span property="priceCurrency" content="BRL"></span></div>"""
r = autopsy.rdfa_row(soup(RD), "u")
check("rdfa price", r and r["price"], "15.0")
check("rdfa name", r and r["product_name"], "Cafe 500g")

# ---- charset ----
check("charset from http header",
      autopsy.declared_charset(
          b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=EUC-JP\r\n", b""),
      "euc-jp")
check("charset from meta",
      autopsy.declared_charset(b"HTTP/1.1 200 OK\r\n",
                               b'<meta charset="Shift_JIS">'), "shift_jis")
check("charset utf-8 -> no redecode",
      autopsy.decode_declared(b"Content-Type: text/html; charset=utf-8", b"x")[2],
      False)

body = b'<meta charset="Shift_JIS"><p>' + "商品価格".encode("shift_jis") + b"</p>"
alt, cs, differs = autopsy.decode_declared(b"HTTP/1.1 200 OK\r\n", body)
check("shift_jis differs from default", differs, True)
check("shift_jis decodes correctly", alt and "商品価格" in alt, True)
check("default decode mangles it", "商品価格" in autopsy.decode_default(body), False)

# ---- WARC envelope ----
warc = gzip.compress(
    b"WARC/1.0\r\nWARC-Type: response\r\n\r\n"
    b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n"
    b"<html><body>hi</body></html>")
h, b = autopsy.split_warc(warc)
check("split_warc body", b, b"<html><body>hi</body></html>")
check("split_warc headers have status", h.startswith(b"HTTP/1.1 200"), True)
check("split_warc gunzip failure", autopsy.split_warc(b"notgzip")[1], "gunzip_failed")

# ---- miss classification: the fixable/unfixable split ----
H404 = "<html><title>404 Not Found</title><body>Page not found</body></html>"
sig = autopsy.classify_miss(H404, soup(H404),
                            b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n")
check("soft_404 detected", sig["soft_404"], True)
check("verdict soft_404", autopsy.verdict(sig, []), "soft_404")
check("verdict fixable when converted",
      autopsy.verdict(sig, ["microdata"]), "fixable_now")

sig2 = autopsy.classify_miss(
    '<html><body><a href="/x">p</a> Add to Cart '
    '<script src="/skin/frontend/base/default/js.js"></script></body></html>',
    soup('<html><body><a href="/x">p</a> Add to Cart</body></html>'),
    b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n")
check("platform magento1", sig2["platform"], "magento1")
check("has_cart", sig2["has_cart"], True)
check("verdict unexplained", autopsy.verdict(sig2, []), "unexplained")

sig3 = autopsy.classify_miss(
    "<html><body><div id=root></div><script>" + "x" * 5000 + "</script></body></html>",
    soup("<html><body><div id=root></div></body></html>"),
    b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n")
check("verdict client_rendered", autopsy.verdict(sig3, []), "client_rendered")

sig4 = autopsy.classify_miss("x", soup("<p>x</p>"),
                             b"HTTP/1.1 200 OK\r\nContent-Type: image/jpeg\r\n")
check("not_html detected", sig4["not_html"], True)
check("verdict not_html", autopsy.verdict(sig4, []), "not_html")

# ---- the miss sink is written by 32 threads and gzip is not thread-safe ----
SINKPATH = os.path.join(os.environ.get("TMPDIR", "/tmp"), "autopsy_sinktest.gz")
N = 4000
with gzip.open(SINKPATH, "wt", encoding="utf-8") as sink:
    def _w(i):
        line = json.dumps({"u": "u%d" % i, "html": "x" * 200})
        with autopsy.SINK_LOCK:
            sink.write(line + "\n")
    with ThreadPoolExecutor(max_workers=32) as ex:
        list(ex.map(_w, range(N)))
rows = [json.loads(x) for x in gzip.open(SINKPATH, "rt")]
check("sink survives 32 threads", len(rows), N)
check("sink lines all distinct", len(set(x["u"] for x in rows)), N)
os.unlink(SINKPATH)

# ---- summarise on a realistic mixed batch ----
out = [
    {"status": "ok", "hit": True, "tier": "jsonld", "s": "a", "c": "C1", "g": "head"},
    {"status": "ok", "hit": False, "s": "a", "c": "C1", "g": "head",
     "sig": {"platform": "magento1", "charset": "euc-jp", "has_itemprop": True,
             "has_ldjson_script": False, "has_price_meta": False,
             "has_cart": True, "soft_404": False, "not_html": False},
     "converted_by": ["microdata", "namefill"], "verdict": "fixable_now",
     "sample": {"microdata": {"price": "1.00"}}},
    {"status": "fetch_failed", "s": "b", "c": "C1", "g": "tail"},
]
res = autopsy.summarise(out, 12.0)
check("summarise n_ok", res["n_ok"], 2)
check("summarise n_miss", res["n_miss"], 1)
check("summarise converted ANY", res["converted"]["ANY"], 1)
check("summarise converted microdata", res["converted"]["microdata"], 1)
check("summarise verdicts", res["verdicts"], {"fixable_now": 1})
check("summarise statuses", res["statuses"]["fetch_failed"], 1)
check("summarise by_crawl hit", res["by_crawl"]["C1"]["hit"], 1)
check("summarise examples", len(res["examples"]), 1)

print()
if FAILED:
    print("%d FAILURES" % len(FAILED))
    for n, g, w in FAILED:
        print("  %s: got %r want %r" % (n, g, w))
    sys.exit(1)
print("all checks passed")

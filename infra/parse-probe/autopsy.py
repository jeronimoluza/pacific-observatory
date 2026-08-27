"""Miss autopsy: what is in the ~50% of archived pages the ladder cannot read.

The parse probe measured *that* half the archive is unreadable. This measures
*why*, and it does so by building the candidate fixes rather than by counting
proxies for them: each candidate tier runs against the pages the current ladder
missed, so its value is a converted-miss count, not an inference from "this
page contains the string itemprop".

Four candidates, cheapest first:
  microdata  - inline schema.org (``<span itemprop="price">``). The current
               meta tier only scans ``<meta>`` tags, so inline microdata -- the
               dominant syntax 2011-2016 -- is invisible to it today.
  rdfa       - ``property="schema:price"`` and friends, same blind spot.
  charset    - re-decode with the declared charset instead of utf-8/latin-1.
               Our two largest sources by URL count are Japanese.
  namefill   - pages that yield a price but no name, which the ladder drops.
               Fills the name from og:title/h1/title.

Misses are also classified as fixable or not: a category page, a soft 404 or a
client-rendered price is not a parser bug, and counting it as one invents a
ceiling we can never reach.

Miss HTML is archived to S3 so later parser work is testable offline instead of
costing an EC2 round trip per idea.
"""
import collections
import gzip
import json
import os
import re
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pool

import boto3
from botocore.config import Config

sys.path.insert(0, "/tmp/parse")

from archived import row_from_meta, rows_from_jsonld, normalize_price  # noqa: E402
from archived_embedded import rows_from_next_flight                    # noqa: E402
from selectors_mod import extract_with_fallback, get_selectors         # noqa: E402
from bs4 import BeautifulSoup                                          # noqa: E402

SRC_BUCKET = "commoncrawl"
OUT_BUCKET = os.environ.get("OUT_BUCKET", "@@OUT_BUCKET@@")
SAMPLE = "/tmp/probe_sample.jsonl.gz"
RESULT_KEY = os.environ.get("RESULT_KEY", "parse-probe/autopsy.json")
MISS_PREFIX = os.environ.get("MISS_PREFIX", "parse-probe/miss-html/")
N_PROC = int(os.environ.get("N_PROC", "2"))
N_THREAD = int(os.environ.get("N_THREAD", "32"))
MAX_STORE = 400000

SINK_LOCK = threading.Lock()
_S3 = None


def s3():
    global _S3
    if _S3 is None:
        _S3 = boto3.client("s3", config=Config(
            max_pool_connections=N_THREAD * 4,
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=15, read_timeout=60))
    return _S3


# ---------- fetch and decode ----------

_CHARSET_HDR = re.compile(rb"charset\s*=\s*[\"']?([\w\-]+)", re.I)
_CHARSET_META = re.compile(rb"<meta[^>]+charset\s*=\s*[\"']?([\w\-]+)", re.I)


def fetch(rec):
    try:
        return s3().get_object(
            Bucket=SRC_BUCKET, Key=rec["f"],
            Range="bytes=%d-%d" % (rec["o"], rec["o"] + rec["l"] - 1),
        )["Body"].read()
    except Exception:
        return None


def split_warc(raw):
    """(http_headers_bytes, body_bytes), or (None, reason) on failure."""
    try:
        blob = gzip.decompress(raw)
    except Exception:
        return None, "gunzip_failed"
    i = blob.find(b"\r\n\r\n")
    if i < 0:
        return None, "no_warc_envelope"
    j = blob.find(b"\r\n\r\n", i + 4)
    if j < 0:
        return None, "no_http_headers"
    body = blob[j + 4:]
    if not body.strip():
        return None, "empty_body"
    return blob[i + 4:j], body


def decode_default(body):
    """What the probe did: utf-8, then latin-1."""
    for enc in ("utf-8", "latin-1"):
        try:
            return body.decode(enc)
        except UnicodeDecodeError:
            continue
    return body.decode("utf-8", "replace")


def declared_charset(headers, body):
    m = _CHARSET_HDR.search(headers or b"")
    if m:
        return m.group(1).decode("ascii", "ignore").lower()
    m = _CHARSET_META.search(body[:4096])
    if m:
        return m.group(1).decode("ascii", "ignore").lower()
    return None


def decode_declared(headers, body):
    """(text, charset_used, differs_from_default)."""
    cs = declared_charset(headers, body)
    if not cs or cs.replace("_", "-") in ("utf-8", "utf8"):
        return None, cs, False
    try:
        return body.decode(cs), cs, True
    except (UnicodeDecodeError, LookupError):
        return None, cs, False


# ---------- the current ladder ----------

SELCACHE = {}


def selectors_for(spider):
    if spider not in SELCACHE:
        try:
            SELCACHE[spider] = get_selectors(spider)
        except Exception:
            SELCACHE[spider] = {}
    return SELCACHE[spider]


def current_ladder(html, url, selectors):
    """(hit, tier) under the shipped fall-through ladder."""
    if selectors:
        soup = BeautifulSoup(html, "html.parser")
        out = {}
        for field, sel_list in selectors.items():
            v = extract_with_fallback(soup, sel_list)
            if v:
                out[field] = v
        if out.get("price"):
            return True, "selectors"
    if rows_from_jsonld(html, url):
        return True, "jsonld"
    if row_from_meta(html, url):
        return True, "meta"
    if rows_from_next_flight(html, url):
        return True, "next_flight"
    return False, None


# ---------- candidate tier: inline microdata ----------

_PRICE_PROPS = ("price", "lowprice", "highprice")


def _prop_of(el, attr):
    v = el.get(attr)
    if isinstance(v, list):
        v = " ".join(v)
    return (v or "").strip().lower()


def _itemprop_value(el):
    v = el.get("content")
    if v:
        return v
    if el.name in ("meta", "link"):
        return el.get("href") or None
    return el.get_text(" ", strip=True) or None


def _positive(price):
    if not price:
        return False
    try:
        return float(price) > 0
    except (TypeError, ValueError):
        return False


def microdata_row(soup, url):
    """Row from inline schema.org microdata, scoped to a Product when present."""
    scope = None
    for el in soup.find_all(attrs={"itemtype": True}):
        if "schema.org/product" in _prop_of(el, "itemtype"):
            scope = el
            break
    root = scope if scope is not None else soup
    price = cur = None
    for el in root.find_all(attrs={"itemprop": True}):
        prop = _prop_of(el, "itemprop")
        if price is None and prop in _PRICE_PROPS:
            price = normalize_price(_itemprop_value(el))
        elif cur is None and prop == "pricecurrency":
            cur = _itemprop_value(el)
    if not _positive(price):
        return None
    name = None
    if scope is not None:
        for el in scope.find_all(attrs={"itemprop": True}):
            if _prop_of(el, "itemprop") == "name":
                name = _itemprop_value(el)
                if name:
                    break
    return {"price": price, "currency": cur, "product_name": name, "url": url}


# ---------- candidate tier: RDFa ----------

def rdfa_row(soup, url):
    price = cur = name = None
    for el in soup.find_all(attrs={"property": True}):
        prop = _prop_of(el, "property").split(":")[-1]
        val = el.get("content") or el.get_text(" ", strip=True)
        if price is None and prop in _PRICE_PROPS:
            price = normalize_price(val)
        elif cur is None and prop == "pricecurrency":
            cur = val
        elif name is None and prop == "name":
            name = val
    if not _positive(price):
        return None
    return {"price": price, "currency": cur, "product_name": name, "url": url}


# ---------- name backfill ----------

def name_from_page(soup):
    for prop in ("og:title", "twitter:title"):
        el = (soup.find("meta", attrs={"property": prop})
              or soup.find("meta", attrs={"name": prop}))
        if el and el.get("content"):
            return el["content"].strip()[:500], prop
    for tag in ("h1", "title"):
        el = soup.find(tag)
        if el:
            t = el.get_text(" ", strip=True)
            if t:
                return t[:500], tag
    return None, None


# ---------- is this miss even fixable ----------

_SOFT404 = re.compile(
    r"\b(404|not found|page not found|no existe|introuvable|nicht gefunden|"
    r"ページが見つかりません|找不到|sayfa bulunamad)", re.I)
_CART = re.compile(
    r"(add to cart|add to basket|buy now|añadir al carrito|agregar al carrito|"
    r"ajouter au panier|in den warenkorb|カートに入れる|加入購物車|加入购物车|"
    r"장바구니|thêm vào giỏ|เพิ่มลงตะกร้า)", re.I)
_SCRIPTS = re.compile(r"<script[\s\S]*?</script>")
_PLATFORMS = (
    ("magento1", re.compile(r"/skin/frontend/|Mage\.Cookies|var/Mage")),
    ("magento2", re.compile(r"/static/version\d|Magento_Ui|mage/requirejs")),
    ("prestashop", re.compile(r"prestashop|/themes/[^/]+/cache/", re.I)),
    ("opencart", re.compile(r"route=product/product|catalog/view/theme")),
    ("oscommerce", re.compile(r"osCsid|product_info\.php")),
    ("shopify", re.compile(r"cdn\.shopify\.com|Shopify\.theme")),
    ("woocommerce", re.compile(r"woocommerce|wp-content/plugins/woo", re.I)),
    ("vtex", re.compile(r"vtexassets|vtexcommercestable", re.I)),
    ("nextjs", re.compile(r"__NEXT_DATA__|/_next/static")),
    ("nuxt", re.compile(r"__NUXT__|/_nuxt/")),
)


def classify_miss(html, soup, headers):
    """Signals present on a page the ladder could not read."""
    sig = {}
    head = (headers or b"").decode("latin-1", "replace")
    parts = head.split(" ", 2)
    sig["http_status"] = parts[1] if head.startswith("HTTP/") and len(parts) > 1 else ""
    ctype = ""
    for line in head.split("\r\n"):
        if line.lower().startswith("content-type:"):
            ctype = line.split(":", 1)[1].strip().split(";")[0].lower()
            break
    sig["content_type"] = ctype
    sig["not_html"] = bool(ctype) and "html" not in ctype
    text = soup.get_text(" ", strip=True) if soup else ""
    sig["text_len"] = len(text)
    sig["n_tags"] = html.count("<")
    sig["has_cart"] = bool(_CART.search(text[:20000]))
    title = soup.find("title") if soup else None
    sig["soft_404"] = (bool(_SOFT404.search(title.get_text() if title else ""))
                       or bool(_SOFT404.search(text[:400])))
    sig["has_ldjson_script"] = "application/ld+json" in html
    sig["has_itemprop"] = "itemprop" in html
    sig["has_price_meta"] = "product:price:amount" in html or "og:price" in html
    sig["script_ratio"] = round(
        sum(len(s) for s in _SCRIPTS.findall(html)) / max(1, len(html)), 3)
    sig["platform"] = next((n for n, p in _PLATFORMS if p.search(html)), None)
    return sig


def verdict(sig, converted_by):
    if converted_by:
        return "fixable_now"
    if sig["not_html"]:
        return "not_html"
    if sig["soft_404"]:
        return "soft_404"
    if sig["text_len"] < 200 and sig["script_ratio"] > 0.5:
        return "client_rendered"
    if not sig["has_cart"]:
        return "probably_not_product_page"
    return "unexplained"


# ---------- per-record work ----------

def one(rec, sink):
    raw = fetch(rec)
    base = {"s": rec["s"], "c": rec["c"], "g": rec["g"]}
    if raw is None:
        return dict(base, status="fetch_failed")
    headers, body = split_warc(raw)
    if headers is None:
        return dict(base, status=body)
    html = decode_default(body)
    url = rec["u"]
    try:
        hit, tier = current_ladder(html, url, selectors_for(rec["s"]))
    except Exception as ex:
        return dict(base, status="parse_error", err=str(ex)[:120])
    if hit:
        return dict(base, status="ok", hit=True, tier=tier)

    # ---- it is a miss: find out why, and what would convert it ----
    soup = BeautifulSoup(html, "html.parser")
    sig = classify_miss(html, soup, headers)
    conv = []
    sample = {}
    try:
        md = microdata_row(soup, url)
    except Exception:
        md = None
    if md:
        conv.append("microdata")
        sample["microdata"] = md
    else:
        try:
            rd = rdfa_row(soup, url)
        except Exception:
            rd = None
        if rd:
            conv.append("rdfa")
            sample["rdfa"] = rd
    alt, cs, differs = decode_declared(headers, body)
    sig["charset"] = cs
    if differs and alt:
        try:
            hit2, tier2 = current_ladder(alt, url, selectors_for(rec["s"]))
        except Exception:
            hit2, tier2 = False, None
        if hit2:
            conv.append("charset")
            sample["charset"] = {"tier": tier2, "charset": cs}
    row = md or sample.get("rdfa")
    if row and not row.get("product_name"):
        nm, src = name_from_page(soup)
        if nm:
            conv.append("namefill")
            sample["namefill"] = {"name": nm, "source": src}
    if sink is not None and len(html) <= MAX_STORE:
        line = json.dumps({"u": url, "s": rec["s"], "c": rec["c"],
                           "charset": cs, "html": html}, ensure_ascii=False)
        # GzipFile.write is not thread-safe and 32 threads share this sink;
        # unsynchronised writes interleave and corrupt the archive.
        with SINK_LOCK:
            sink.write(line + "\n")
    return dict(base, status="ok", hit=False, sig=sig,
                converted_by=conv, verdict=verdict(sig, conv), sample=sample)


def chunk(args):
    idx, recs = args
    path = "/tmp/miss_%d_%d.jsonl.gz" % (os.getpid(), idx)
    with gzip.open(path, "wt", encoding="utf-8") as sink:
        with ThreadPoolExecutor(max_workers=N_THREAD) as ex:
            out = list(ex.map(lambda r: one(r, sink), recs))
    return out, path


# ---------- driver ----------

def summarise(out, wall):
    ok = [r for r in out if r["status"] == "ok"]
    miss = [r for r in ok if not r.get("hit")]
    conv = collections.Counter()
    for r in miss:
        for c in r["converted_by"]:
            conv[c] += 1
        if r["converted_by"]:
            conv["ANY"] += 1

    bc = collections.defaultdict(collections.Counter)
    bs = collections.defaultdict(collections.Counter)
    for r in ok:
        for c in (bc[r["c"]], bs[r["s"]]):
            c["ok"] += 1
            c["hit"] += int(bool(r.get("hit")))
        if not r.get("hit"):
            for x in r["converted_by"]:
                bc[r["c"]]["conv_" + x] += 1
            if r["converted_by"]:
                bc[r["c"]]["conv_ANY"] += 1
                bs[r["s"]]["conv_ANY"] += 1
            bc[r["c"]]["v_" + r["verdict"]] += 1

    examples, seen = [], collections.Counter()
    for r in miss:
        if not r["converted_by"]:
            continue
        key = r["converted_by"][0]
        if seen[key] >= 25:
            continue
        seen[key] += 1
        examples.append({"s": r["s"], "c": r["c"], "by": r["converted_by"],
                         "sample": r["sample"]})

    return {
        "n_records": len(out),
        "wall_seconds": round(wall, 1),
        "statuses": dict(collections.Counter(r["status"] for r in out)),
        "n_ok": len(ok), "n_hit": len(ok) - len(miss), "n_miss": len(miss),
        "converted": dict(conv),
        "verdicts": dict(collections.Counter(r["verdict"] for r in miss)),
        "platforms": dict(collections.Counter(
            r["sig"]["platform"] for r in miss)),
        "charsets": dict(collections.Counter(
            r["sig"].get("charset") for r in miss).most_common(25)),
        "miss_signals": {
            k: sum(1 for r in miss if r["sig"].get(k))
            for k in ("has_ldjson_script", "has_itemprop", "has_price_meta",
                      "has_cart", "soft_404", "not_html")},
        "by_crawl": {k: dict(v) for k, v in sorted(bc.items())},
        "by_source": {k: dict(v) for k, v in sorted(bs.items())},
        "examples": examples,
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def main():
    recs = [json.loads(line) for line in gzip.open(SAMPLE, "rt")]
    print("records: %d  procs: %d  threads: %d" % (len(recs), N_PROC, N_THREAD),
          flush=True)
    nch = N_PROC * 4
    chunks = [(i, recs[i::nch]) for i in range(nch)]

    t0 = time.time()
    out, paths = [], []
    with Pool(N_PROC) as pool:
        for i, (part, p) in enumerate(pool.imap_unordered(chunk, chunks), 1):
            out.extend(part)
            paths.append(p)
            print("  %d/%d  %d recs  %.0f rec/s" % (
                i, nch, len(out), len(out) / (time.time() - t0)), flush=True)
    result = summarise(out, time.time() - t0)

    print("\nok %d  hit %d  miss %d" % (
        result["n_ok"], result["n_hit"], result["n_miss"]))
    print("converted:", result["converted"])
    print("verdicts:", result["verdicts"])

    iid = None
    try:
        iid = imds("instance-id")
        result["instance_id"] = iid
    except Exception:
        pass
    blob = json.dumps(result, indent=2, default=str)
    try:
        boto3.client("s3").put_object(
            Bucket=OUT_BUCKET, Key=RESULT_KEY,
            Body=blob.encode(), ContentType="application/json")
        print("wrote s3://%s/%s" % (OUT_BUCKET, RESULT_KEY), flush=True)
    except Exception as ex:
        print("could not write result:", ex)
    cl = boto3.client("s3")
    for p in paths:
        try:
            if os.path.getsize(p) > 40:
                cl.upload_file(p, OUT_BUCKET, MISS_PREFIX + os.path.basename(p))
        except Exception as ex:
            print("miss upload failed", p, ex)
    print("miss html uploaded", flush=True)
    if iid:
        try:
            boto3.client("ec2").terminate_instances(InstanceIds=[iid])
        except Exception:
            os.system("shutdown -h now")


def imds(path):
    tok = urllib.request.urlopen(urllib.request.Request(
        "http://169.254.169.254/latest/api/token", method="PUT",
        headers={"X-aws-ec2-metadata-token-ttl-seconds": "300"}),
        timeout=5).read().decode()
    return urllib.request.urlopen(urllib.request.Request(
        "http://169.254.169.254/latest/meta-data/" + path,
        headers={"X-aws-ec2-metadata-token": tok}), timeout=5).read().decode()


if __name__ == "__main__":
    main()

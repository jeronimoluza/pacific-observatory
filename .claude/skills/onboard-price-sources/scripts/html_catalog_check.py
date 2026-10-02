#!/usr/bin/env python3
"""HTML-catalog fallback for hosts with no open platform endpoint.

Run it on whatever the JSON probes filed no_catalog. On Jamaica's 139 such
hosts it recovered two sealed ground-truth sources (fontanapharmacy.com by
category tree, shopsampars.com by page 2) and surfaced 16 price-dense pages
for an agent to adjudicate, about 5 of them real consumer catalogs.

    # on a8
    ~/venv/bin/python scripts/html_catalog_check.py hosts.txt out.jsonl \\
        --currency JMD --symbol 'J$'

The bar (from the A/B brief): a server-rendered listing where a second page
returns a different product set AND a price is read off a product. "Second
page" is either page 2 of one listing, or a second category page: a catalog
enumerated by category tree is as enumerable as one enumerated by page number.

Tiers written per host:
  html_catalog   two listing pages, both priced, the second adds >= 5 products
  price_dense    a listing page carries >= 5 prices; enumerability not proven
  needs_browser  big HTML, almost no same-host links, no prices: a JS app shell
  none           nothing price-shaped found
  unfetched      root never answered 200 HTML
"""

import argparse
import html as htmllib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

from curl_cffi import requests as rq

PROFILES = ["chrome124", "firefox133"]
TAG = re.compile(r"<[^>]+>")
# Any currency-looking amount with cents: "$", "US$", "FJ$", "EUR", "€", "£".
ANY_PRICE = re.compile(r"(?:[A-Z]{0,3}\$|[A-Z]{3}\s|€|£)\s?\d[\d,]*\.\d{2}")


def local_price_re(code, symbols=()):
    """Prices in the country's own currency, matched on tag-stripped text.

    WooCommerce puts the symbol and the number in separate spans, and Fontana
    writes "$18,800.00 JMD", so the code is accepted before or after the number.
    """
    lead = "|".join([re.escape(s) for s in symbols] + [re.escape(code)])
    return re.compile(
        r"(?:%s)\s?\d[\d,]*(?:\.\d{2})?|\$\s?\d[\d,]*(?:\.\d{2})?\s?%s"
        % (lead, re.escape(code))
    )


HREF = re.compile(r'href="([^"#]+)"', re.I)
LISTING = re.compile(
    r"/(shop|products?|collections?|category|categories|product-category|catalog|"
    r"store|departments?|c/|aisles?|groceries|pharmacy|furniture|appliances)",
    re.I,
)
PRODUCT = re.compile(r"/(product|products|p|item|dp)/[^/?]+", re.I)
ASSET = re.compile(r"\.(css|js|png|jpe?g|gif|svg|webp|ico|woff2?)(\?|$)", re.I)
NEXT = re.compile(
    r'<link[^>]+rel="next"[^>]+href="([^"]+)"|<a[^>]+rel="next"[^>]+href="([^"]+)"',
    re.I,
)
PAGE2_HINT = re.compile(
    r'href="([^"]*(?:[?&](?:amp;)?(?:page|p|pg|paged)=2\b|/page/2/?)[^"]*)"', re.I
)


def get(url):
    for prof in PROFILES:
        try:
            r = rq.get(url, impersonate=prof, timeout=20, allow_redirects=True)
        except Exception:
            continue
        if r.status_code == 200 and "html" in r.headers.get("content-type", "").lower():
            return r.text or ""
    return None


def prices(html, local):
    """Distinct non-zero prices. A cart widget repeats "$0.00" on every page and
    once passed the bar on its own (blingersja.com, 16 matches, 1 real value)."""
    text = htmllib.unescape(TAG.sub(" ", html))

    def real(found):
        return sorted({p for p in found if re.search(r"[1-9]", p)})

    return real(local.findall(text)), real(ANY_PRICE.findall(text))


def product_links(html, base):
    host = urlparse(base).netloc
    out = set()
    for h in HREF.findall(html):
        u = urljoin(base, h)
        if urlparse(u).netloc == host and PRODUCT.search(urlparse(u).path):
            out.add(u.split("?")[0].rstrip("/"))
    return out


def page2_url(html, url):
    m = NEXT.search(html)
    if m:
        return urljoin(url, htmllib.unescape(m.group(1) or m.group(2)))
    m = PAGE2_HINT.search(html)
    if m:
        return urljoin(url, htmllib.unescape(m.group(1)))
    return None


def adds_products(first, second):
    # Sites repeat a featured block on every listing, so overlap is always high.
    # What proves enumeration is that the second page adds products the first lacks.
    return len(second - first) >= 5


def check(host, local):
    base = "https://%s/" % host
    res = {
        "host": host,
        "tier": "none",
        "how": None,
        "listing": None,
        "second": None,
        "local_prices": 0,
        "any_prices": 0,
        "sample": None,
    }
    root = get(base)
    if root is None:
        res["tier"] = "unfetched"
        return res

    bare = host.replace("www.", "")
    same = [urljoin(base, h) for h in HREF.findall(root)]
    same = [
        u for u in same if urlparse(u).netloc.endswith(bare) and not ASSET.search(u)
    ]
    listings = []
    for u in same:
        if LISTING.search(urlparse(u).path) and u not in listings:
            listings.append(u)

    priced = []  # (url, product_links, loc, anyp) for listing pages with >= 3 prices
    best = None
    for url in [base] + listings[:6]:
        html = root if url == base else get(url)
        if not html:
            continue
        loc, anyp = prices(html, local)
        n = max(len(loc), len(anyp))
        if best is None or n > best[1]:
            best = (url, n, loc, anyp)
        if n < 3:
            continue
        links = product_links(html, url)
        p2 = page2_url(html, url)
        if p2:
            html2 = get(p2)
            if html2:
                loc2, any2 = prices(html2, local)
                if max(len(loc2), len(any2)) >= 3 and adds_products(
                    links, product_links(html2, p2)
                ):
                    res.update(
                        tier="html_catalog",
                        how="page2",
                        listing=url,
                        second=p2,
                        local_prices=len(loc),
                        any_prices=len(anyp),
                        sample=(loc or anyp)[0],
                    )
                    return res
        if url != base:
            for prev_url, prev_links, _, _ in priced:
                if adds_products(prev_links, links):
                    res.update(
                        tier="html_catalog",
                        how="category_pair",
                        listing=prev_url,
                        second=url,
                        local_prices=len(loc),
                        any_prices=len(anyp),
                        sample=(loc or anyp)[0],
                    )
                    return res
            priced.append((url, links, loc, anyp))

    if best and best[1] >= 5:
        url, n, loc, anyp = best
        res.update(
            tier="price_dense",
            listing=url,
            local_prices=len(loc),
            any_prices=len(anyp),
            sample=(loc or anyp)[0],
        )
    elif len(root) > 30000 and len(set(same)) < 60:
        res["tier"] = "needs_browser"
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("hosts", help="file, one host per line")
    ap.add_argument("out", help="JSONL written here, one row per host")
    ap.add_argument("--currency", required=True, help="ISO code, e.g. JMD, FJD")
    ap.add_argument(
        "--symbol", action="append", default=[], help="e.g. J$ (repeatable)"
    )
    args = ap.parse_args()
    local = local_price_re(args.currency, args.symbol)
    hosts = [h.strip() for h in open(args.hosts) if h.strip()]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda h: check(h, local), hosts))
    with open(args.out, "w") as fh:
        for r in results:
            fh.write(json.dumps(r) + "\n")
    counts = {}
    for r in results:
        counts[r["tier"]] = counts.get(r["tier"], 0) + 1
    print("hosts %d  %s" % (len(results), counts))
    for tier in ("html_catalog", "price_dense", "needs_browser"):
        rows = [r for r in results if r["tier"] == tier]
        print("\n== %s (%d)" % (tier, len(rows)))
        for r in sorted(rows, key=lambda x: (-x["local_prices"], -x["any_prices"])):
            print(
                "  %-30s %-13s local=%-3d any=%-3d %-18s %s"
                % (
                    r["host"],
                    r["how"] or "",
                    r["local_prices"],
                    r["any_prices"],
                    (r["sample"] or "")[:18],
                    (r["second"] or r["listing"] or "")[:60],
                )
            )


if __name__ == "__main__":
    main()

"""
Alphamega Hypermarkets (Cyprus) — https://www.alphamega.com.cy/.

Bespoke .NET/ASP storefront ("Swift" template) with no WooCommerce/Shopify/
Magento/VTEX surface, but the site wires its on-site search widget to a
public Unbxd Search-as-a-Service index (search.unbxd.io) that exposes the
FULL catalog unauthenticated via `q=*`. Credentials are hardcoded client-side
JS, not secret: siteKey/apiKey pulled from
cdn.alphamega.com.cy/.../Assets/js/custom.js (`GetUnbxdSiteNameNT()` /
`GetUnbxdApiKeyNT()`, prod values below). Confirmed live 2026-08-31:
numberOfProducts=15,317; rows=100 is the server-enforced page cap (asking
for more silently truncates to 100); `start` pagination advances correctly
across pages (verified 4 pages, 400 distinct uniqueId, zero overlap).

Response fields used: id/sku/uniqueId (all equal), title, price (decimal,
already EUR — currency field confirmed "EUR" on every sampled row),
categoryPath (pipe of "A>B>C" strings, first taken), availability
("true"/"false" string), productUrl (canonical alphamega.com.cy link).
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

SITE_KEY = "ss-unbxd-auk-alphamega-en-prod51051734415860"
API_KEY = "b2fe883192293321a4225f18fb8c26af"
SEARCH_URL = f"https://search.unbxd.io/{API_KEY}/{SITE_KEY}/search"
ROWS = 100
MAX_START = 20000  # safety cap well above the 15,317 known catalog size

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(s: str) -> str:
    return _SLUG_RE.sub("-", s.lower()).strip("-")


def _build_product_url(title: str, category_paths: list) -> str | None:
    """Reconstruct the live friendly PDP URL.

    The feed's own `productUrl` field (a `Default.aspx?ID=6751&ProductId=`
    query-string link) is DEAD on every sampled row -- 404s from the CDN
    even with a warmed session/cookies, apparently a legacy route the site
    no longer serves though the search feed was never updated. The live
    site's own rendered listing/category pages instead use friendly URLs
    of the shape /en/groceries/<slugified-category-path>/<slugified-title>
    (confirmed against real listing-page hrefs, e.g. "Hydrogen Peroxide
    Solution 6% w/v 20Vol 50 ml" in "Personal Care>Medical
    Products>Plasters & First Aid" -> .../personal-care/medical-products/
    plasters-first-aid/hydrogen-peroxide-solution-6-w-v-20vol-50-ml).
    Reconstructing it this way and re-probing a random sample of 15 live
    products gave 14/15 = 93% resolving 200; the deepest entry in
    categoryPath (most ">"-separated segments) is used since the field's
    ordering (shallow-to-deep vs deep-to-shallow) is inconsistent across
    rows.
    """
    if not category_paths:
        return None
    deepest = max(category_paths, key=lambda c: c.count(">"))
    segs = [_slugify(s) for s in deepest.split(">")]
    return (
        f"https://www.alphamega.com.cy/en/groceries/{'/'.join(segs)}/{_slugify(title)}"
    )


class AlphamegaCySpider(scrapy.Spider):
    name = "alphamega_cy"
    allowed_domains = ["unbxd.io", "search.unbxd.io"]
    currency = "EUR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def _page_url(self, start: int) -> str:
        return f"{SEARCH_URL}?q=*&rows={ROWS}&start={start}"

    async def start(self):
        yield scrapy.Request(
            self._page_url(0), callback=self.parse_page, meta={"start": 0}
        )

    def parse_page(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON response at {response.url}")
            return
        resp = data.get("response") or {}
        products = resp.get("products") or []
        start = response.meta["start"]
        total = resp.get("numberOfProducts", 0)
        logger.info(f"{self.name} start={start} count={len(products)} total={total}")
        for p in products:
            item = self._item(p)
            if item:
                yield item
        next_start = start + ROWS
        if products and next_start < total and next_start < MAX_START:
            yield scrapy.Request(
                self._page_url(next_start),
                callback=self.parse_page,
                meta={"start": next_start},
            )

    def _item(self, p: dict):
        name = p.get("title")
        price = p.get("price")
        if not name or price is None:
            return None
        cat_paths = p.get("categoryPath") or []
        category = cat_paths[0].replace(">", " > ") if cat_paths else None
        availability = str(p.get("availability", "true")).lower()
        clean_name = html.unescape(str(name)).strip()
        url = _build_product_url(clean_name, cat_paths) or p.get("productUrl") or ""
        return {
            "product_id": str(p.get("uniqueId") or p.get("sku") or p.get("id")),
            "product_name": clean_name[:500],
            "category": category,
            "price": str(price),
            "currency": p.get("currency") or self.currency,
            "available": availability == "true",
            "url": url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

"""
Spider for ePRICE (Italy) -- https://www.eprice.it/.

Custom PHP/JSP storefront behind Akamai (bare requests 403 AkamaiGHost;
curl_cffi impersonate=chrome124 clears both homepage and category pages
cleanly, verified live 2026-08-17). Product name+price are server-rendered
in plain HTML listing markup, no API needed.

This is a genuine retail marketplace, not a price-comparison aggregator:
each listing card carries exactly one price (no "confronta prezzi" /
multi-store comparison UI), and product detail pages show a real
add-to-cart flow with a "Venduto e spedito da <seller>" fulfillment line
(third-party marketplace sellers, Amazon-Marketplace-style -- not competing
offers from external sites). analytical_role: retailer_sku is warranted.

Category discovery: the 16 top-level category slugs linked from the
homepage nav (all electronics/appliances -- smartphone, smart-tv,
computer-portatile, frigorifero, lavatrice, ...). A fuller category set is
available via the site's per-department XML sitemaps
(sitemap/https/SiteMapIndex_20110310.xml) if the full scrape needs more
depth; this scaffold uses the nav set.

Pagination is the `pp` query param (robots.txt explicitly allows
`/pr/*?pp=*`), NOT `page` -- `?page=2` silently returns page 1 again
unchanged; `?pp=2` returns a disjoint product set. Enumerability proven:
/pr/smartphone (pp=1 implicit) vs /pr/smartphone?pp=2 return 36 + 36
distinct product ids, zero overlap. An out-of-range page (pp=77 for a
76-page category) returns 200 with zero product blocks, giving a clean
stop condition.

Product blocks are delimited by `<div sku="...">`; name from the block's
`title="..."` attribute, price from the first `ep_itemPrice">EUR AMOUNT`
in the block. Prices use Italian decimal formatting (comma decimal,
dot/none thousands separator).
"""

import html
import re
from datetime import datetime, timezone

import scrapy

_BASE = "https://www.eprice.it"
_CATEGORIES = [
    "monitor",
    "asciugatrice",
    "aspirapolvere",
    "frigorifero",
    "ferro-da-stiro",
    "computer-fisso",
    "stampante",
    "lavatrice",
    "fotocamera",
    "iphone",
    "macchina-caffe",
    "smartphone",
    "smart-tv",
    "computer-portatile",
    "tablet",
    "forno-microonde",
]
_SKU_RE = re.compile(r'<div sku="(\d+)" rel="[^"]*" title="([^"]+)"')
_PRICE_RE = re.compile(r'ep_itemPrice">\s*€?\s*([\d.,]+)')
_MAX_PAGES = 30


class EpriceItSpider(scrapy.Spider):
    name = "eprice_it"
    allowed_domains = ["eprice.it"]
    currency = "EUR"
    language = "it"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }
    IMPERSONATE_PROFILE = "chrome124"

    async def start(self):
        for category in _CATEGORIES:
            yield self._page_request(category, 1)

    def _page_request(self, category: str, page: int):
        url = (
            f"{_BASE}/pr/{category}"
            if page == 1
            else f"{_BASE}/pr/{category}?pp={page}"
        )
        return scrapy.Request(
            url,
            callback=self.parse_listing,
            meta={
                "category": category,
                "page": page,
                "impersonate": self.IMPERSONATE_PROFILE,
            },
        )

    def parse_listing(self, response):
        category = response.meta["category"]
        page = response.meta["page"]
        blocks = re.split(r'(?=<div sku=")', response.text)[1:]
        found = 0
        for block in blocks:
            item = self._item(block, category)
            if item:
                found += 1
                yield item
        if found and page < _MAX_PAGES:
            yield self._page_request(category, page + 1)

    def _item(self, block: str, category: str):
        sku_match = _SKU_RE.match(block)
        if not sku_match:
            return None
        price_match = _PRICE_RE.search(block[:3000])
        if not price_match:
            return None
        product_id = sku_match.group(1)
        name = html.unescape(sku_match.group(2)).strip()
        price = price_match.group(1).replace(".", "").replace(",", ".")
        if not name or not price:
            return None
        return {
            "product_id": product_id,
            "product_name": name[:500],
            "category": category,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": f"{_BASE}/d-{product_id}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

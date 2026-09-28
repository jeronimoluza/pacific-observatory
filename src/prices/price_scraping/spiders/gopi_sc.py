"""GOPI Veg. Food & General Merchants (Seychelles) -- https://www.gopi.shop/

Wix Stores grocery/general-merchandise catalogue (Shreeji Group), Mahe.
Server-rendered -- no Playwright needed. The `/products?page=N` listing
(the site's "all products" collection, `totalCount: 1379` seen in the
embedded gallery state 2026-09-28) carries plain
`<a href="/product-page/<slug>">` links in the raw HTML from a bare
`curl_cffi` GET, same pattern as aradamart_et (Ethiopia, also Wix). Every
`/product-page/<slug>` PDP embeds a Schema.org Product JSON-LD block with
`name`, `sku`, `offers.price` / `offers.priceCurrency` -- no CSS selectors
needed.

Verified live 2026-09-28: page 1 and page 2 of `/products` return 24
product links each with zero overlap -- pagination is real, not a
carousel. Sample PDP (kerrygold-red-cheddar-slices-150g) JSON-LD:
priceCurrency "SCR", price "36", availability schema.org/OutOfStock (item
happened to be out of stock at probe time -- `available` still emitted
per the availability field, not skipped).

Category nav pages (/fresh-food, /frozenfood, /drinks, /food-cupboard,
/household, /health-beauty, /babycare, /homeoutdoor) exist and also carry
product-page links, but `/products` alone is the full catalogue walk (24
per page, ceil(1379/24) = 58 pages) so this spider only walks that one
listing to avoid re-fetching the same PDPs under multiple categories.

No reliable breadcrumb/category on the PDP itself -- left null rather than
invented from the nav (same call as aradamart_et).
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.gopi.shop"
_PAGE_SIZE = 24
_TOTAL_COUNT = 1379  # observed 2026-09-28; drives MAX_PAGES, re-check periodically
_MAX_PAGES = -(-_TOTAL_COUNT // _PAGE_SIZE)  # ceil
_PRODUCT_LINK_RE = re.compile(r'href="(?:https://www\.gopi\.shop)?(/product-page/[^"?#]+)"')


class GopiScSpider(scrapy.Spider):
    name = "gopi_sc"
    allowed_domains = ["www.gopi.shop", "gopi.shop"]
    currency = "SCR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_urls: set[str] = set()

    async def start(self):
        for page in range(1, _MAX_PAGES + 1):
            yield scrapy.Request(
                f"{_BASE}/products?page={page}",
                callback=self.parse_listing,
                cb_kwargs={"page": page},
            )

    def parse_listing(self, response, page):
        paths = sorted(set(_PRODUCT_LINK_RE.findall(response.text)))
        logger.info(f"gopi_sc: page={page} found {len(paths)} product links")
        for path in paths:
            url = _BASE + path
            if url in self.seen_urls:
                continue
            self.seen_urls.add(url)
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        product = self._extract_json_ld(response)
        if not product:
            logger.warning(f"No Product JSON-LD at {response.url}")
            return
        offers = product.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = offers.get("price")
        currency = offers.get("priceCurrency") or self.currency
        name = product.get("name")
        sku = product.get("sku")
        if not (price and name):
            logger.warning(f"Missing price or name at {response.url}")
            return
        availability = offers.get("availability", "")
        yield {
            "product_id": sku or response.url.rsplit("/", 1)[-1],
            "product_name": str(name).strip()[:500],
            "category": None,
            "price": str(price),
            "currency": currency,
            "available": "OutOfStock" not in availability,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _extract_json_ld(response):
        for raw in response.xpath(
            '//script[@type="application/ld+json"]/text()'
        ).getall():
            try:
                d = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(d, dict) and d.get("@type") == "Product":
                return d
        return None

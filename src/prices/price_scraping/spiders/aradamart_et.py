"""
Spider for Arada Mart (Ethiopia) — https://www.aradamart.net/

Wix Stores grocery-delivery catalogue serving Addis Ababa. Server-rendered:
the `/shop-all?page=N` listing carries plain `<a href="/product-page/<slug>">`
links (absolute on some pages, relative on others — both are matched), and
every `/product-page/<slug>` PDP embeds a Schema.org Product JSON-LD block
with `name`, `sku`, and `offers.price` / `offers.priceCurrency` — no CSS
selectors needed, same pattern as capelle_nr (Nauru, also Wix).

Re-verified live 2026-09-01: GET /shop-all -> 200, `"totalCount":410` in the
embedded Wix gallery state. Page 1 carries 60 product links; pages step
through in batches of 60 down to a final partial page of 50
(6*60 + 50 = 410), confirming page=1..7 walks the full catalogue with no
overlap. `page=2` specifically renders its product-page links as
site-relative hrefs instead of absolute — a Wix SSR-cache quirk, not a
missing page — so the parser matches on the `/product-page/<slug>` path
fragment rather than requiring the full absolute href.

Sample PDP: /product-page/broccoli-ብሮኮሊ-500gm -> JSON-LD name
"Broccoli ብሮኮሊ 500gm", offers.priceCurrency "ETB", offers.price "108".
Amharic (Ge'ez) glosses appear on a subset of produce names alongside the
English name; the catalogue is majority English brand/product names
(e.g. "3D Kids anti cavity toothaste", "Aloha Cocoa Butter Lotion 110g").
No reliable in-page breadcrumb/category exists (Wix's own nav category
slugs, e.g. /fresh-produce, /canned-bottled, are 301-redirecting to stale,
now-404 collection slugs even though the underlying products are still
live under /shop-all) — category is left null per the skill's guidance
rather than invented from a broken nav.

No numeric pagination beyond page 7 (page=8 onward renders the same empty
gallery state) — the crawl stops there.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.aradamart.net"
_MAX_PAGES = 7  # ceil(410 / 60), re-verified live 2026-09-01
_PRODUCT_LINK_RE = re.compile(
    r'href="(?:https://www\.aradamart\.net)?(/product-page/[^"?#]+)"'
)


class AradamartEtSpider(scrapy.Spider):
    name = "aradamart_et"
    allowed_domains = ["www.aradamart.net", "aradamart.net"]
    currency = "ETB"
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
                f"{_BASE}/shop-all?page={page}",
                callback=self.parse_listing,
                cb_kwargs={"page": page},
            )

    def parse_listing(self, response, page):
        paths = sorted(set(_PRODUCT_LINK_RE.findall(response.text)))
        logger.info(f"aradamart_et: page={page} found {len(paths)} product links")
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

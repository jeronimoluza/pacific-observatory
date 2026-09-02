"""
Spider for TuAmbia (Cuba diaspora grocery/general-merchandise delivery site)
-- https://tuambia.com/.

Same shape as the other four Cuba sources: pay abroad (USD), deliver to Cuba.
This is a real, usable Cuba price signal but it is NOT a domestic Cuban
retail price in CUP -- do not treat rows from this source as domestic CUP
retail.

Next.js storefront, server-rendered. Each PDP embeds a schema.org
`application/ld+json` Product block with name/sku/price/priceCurrency
(verified live 2026-09-01, e.g. "Azucar refino, 4 lb, Dixie Crystals" ->
USD 7.64, sku "B-JAM-001-753"). No Playwright needed.

Catalog is enumerable via the sitemap index (https://tuambia.com/sitemap.xml
-> per-category sub-sitemaps). The site serves the *same* catalog mirrored
under three regional URL prefixes (`hab`, `centro`, `occidente` -- Havana,
central Cuba, western Cuba delivery zones); `hab` and `occidente` sitemaps
were confirmed byte-identical in product-slug set on a spot check, and
`centro` is a subset. Only `hab` (Havana) is crawled here, both to match the
Havana focus of the other Cuba sources and because DuplicationPipeline dedups
on `item['url']`, which is region-prefixed -- crawling all three regions
would silently 2-3x the row count with same-SKU duplicates under different
URLs, not new products. 1,169 distinct /hab/catalog/<slug> PDP URLs across
54 category sitemaps (counted live 2026-09-01). Category label comes from the
sitemap file name (e.g. "alimentos", "carnicos-y-embutidos") since PDPs carry
no server-rendered breadcrumb text -- only client-side i18n strings.

Catalog spans groceries, beverages, cleaning/personal care, small appliances,
hardware, and auto accessories (same breadth as mallhabana_cu) -> channel is
marketplace rather than supermarket.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_INDEX = "https://tuambia.com/sitemap.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_JSONLD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
_CATEGORY_RE = re.compile(r"/dynamic/hab/catalog/category/([a-z0-9\-]+)\.xml$")


class TuambiaCuSpider(scrapy.Spider):
    name = "tuambia_cu"
    allowed_domains = ["tuambia.com", "www.tuambia.com"]
    currency = "USD"
    language = "es"

    custom_settings = {
        "IMPERSONATE_BROWSERS": ["chrome124"],
        "CONCURRENT_REQUESTS_PER_DOMAIN": 10,
        "CONCURRENT_REQUESTS": 16,
        "DOWNLOAD_DELAY": 0.2,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 0.2,
        "AUTOTHROTTLE_MAX_DELAY": 5.0,
    }

    async def start(self):
        yield scrapy.Request(
            _SITEMAP_INDEX, callback=self.parse_index, meta={"impersonate": "chrome124"}
        )

    def parse_index(self, response):
        locs = _LOC_RE.findall(response.text)
        hab_sitemaps = [loc for loc in locs if "/dynamic/hab/" in loc]
        logger.info(f"tuambia_cu: {len(hab_sitemaps)} hab category sitemaps")
        for sm in hab_sitemaps:
            m = _CATEGORY_RE.search(sm)
            category = m.group(1) if m else None
            yield scrapy.Request(
                sm,
                callback=self.parse_category_sitemap,
                meta={"impersonate": "chrome124", "category": category},
            )

    def parse_category_sitemap(self, response):
        category = response.meta.get("category")
        urls = _LOC_RE.findall(response.text)
        for url in urls:
            yield scrapy.Request(
                url,
                callback=self.parse_product,
                meta={"impersonate": "chrome124", "category": category},
            )

    def parse_product(self, response):
        m = _JSONLD_RE.search(response.text)
        if not m:
            return
        try:
            data = json.loads(m.group(1))
        except ValueError:
            logger.warning(f"tuambia_cu: bad JSON-LD at {response.url}")
            return
        if data.get("@type") != "Product":
            return
        offers = data.get("offers") or {}
        price = offers.get("price")
        name = (data.get("name") or "").strip()
        if not name or price is None:
            return
        sku = data.get("sku") or data.get("mpn")
        availability = offers.get("availability") or ""
        yield {
            "product_id": str(sku) if sku else response.url,
            "product_name": name[:500],
            "category": response.meta.get("category"),
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": ("InStock" in availability) if availability else True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

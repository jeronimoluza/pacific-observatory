"""
Spider for GAMMA Netherlands — https://www.gamma.nl/ (DIY / home-improvement).

Next.js App Router (React Server Components) storefront. The homepage-nav
route (/assortiment/k/<category>) embeds product cards inside an escaped
`self.__next_f.push(...)` RSC flight string, but that page has no working
pagination (?page=2 / ?p=2 / ?offset=30 all silently returned the same 30
product codes on a live check 2026-08-17) — a repeat of the "guessed
pagination param returns page 1 again" trap. The catalog is walked via the
site's own sitemap instead: robots.txt -> https://sitemap.gamma.nl/index.xml
-> product.xml, 45655 PDP URLs total. URLs come in two families:
`/p/B<id>` (42490 regular SKUs) and `/p/C<id>` (3031 "op maat" / made-to-
-measure configurator pages with no priced offer — filtered out).

Each regular PDP carries a standard `<script type="application/ld+json">`
Product block with `offers.price` / `offers.priceCurrency` — no RSC/devalue
parsing needed for price extraction, unlike the category-card path.
`offers.price` is the plain listed price; `offers.priceSpecification` (when
present) is a members-only "Voordeelpas" tier discount, deliberately not
used here since it isn't the price a non-member pays.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_SKU_URL_RE = re.compile(r"/p/(B\d+)$")
_LDJSON_RE = re.compile(
    r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL
)

_SITEMAP = "https://sitemap.gamma.nl/product.xml"


class GammaNlSpider(scrapy.Spider):
    name = "gamma_nl"
    allowed_domains = ["gamma.nl"]
    currency = "EUR"
    language = "nl"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }
    IMPERSONATE_PROFILE = "chrome124"

    async def start(self):
        yield scrapy.Request(
            _SITEMAP,
            callback=self.parse_sitemap,
            meta={"impersonate": self.IMPERSONATE_PROFILE},
        )

    def parse_sitemap(self, response):
        urls = _LOC_RE.findall(response.text)
        sku_urls = [u for u in urls if _SKU_URL_RE.search(u)]
        logger.info(f"{self.name}: {len(sku_urls)} SKU PDPs of {len(urls)} total URLs")
        for url in sku_urls:
            yield scrapy.Request(
                url,
                callback=self.parse_product,
                meta={"impersonate": self.IMPERSONATE_PROFILE},
            )

    def parse_product(self, response):
        m = _SKU_URL_RE.search(response.url)
        if not m:
            return
        product_id = m.group(1)

        product = None
        for blob in _LDJSON_RE.findall(response.text):
            try:
                data = json.loads(blob)
            except ValueError:
                continue
            if isinstance(data, dict) and data.get("@type") == "Product":
                product = data
                break
        if product is None:
            return

        offers = product.get("offers") or {}
        price = offers.get("price")
        name = product.get("name")
        if not name or price is None:
            return

        yield {
            "product_id": product_id,
            "product_name": name.strip()[:500],
            "category": None,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": offers.get("availability", "").endswith("InStock"),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

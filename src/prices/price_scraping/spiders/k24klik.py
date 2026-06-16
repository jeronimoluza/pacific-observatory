"""
Spider for K24Klik (Indonesia) — online apotek/farmasi.

URL discovery via /sitemap.xml (~9,800 entries; product URLs match /p/<slug>-<id>).
Each product page exposes Schema.org Product JSON-LD with name, sku, brand,
offers.price/priceCurrency/availability — no JS rendering needed.

Replaces the previous scrapy-playwright implementation that opened a headless
Chromium and never logged a single request before timing out the whole run.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

SITEMAP_URL = "https://www.k24klik.com/sitemap.xml"


class K24KlikSpider(scrapy.Spider):
    name = "k24klik"
    allowed_domains = ["www.k24klik.com"]
    currency = "IDR"
    language = "id"

    IMPERSONATE_PROFILE = "safari17_0"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 16,
        "CONCURRENT_REQUESTS": 32,
        "DOWNLOAD_DELAY": 0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": False,
    }

    async def start(self):
        yield scrapy.Request(
            SITEMAP_URL,
            callback=self.parse_sitemap,
            meta={"impersonate": self.IMPERSONATE_PROFILE},
            errback=self.errback,
        )

    def parse_sitemap(self, response):
        urls = response.xpath("//*[local-name()='loc']/text()").getall()
        product_urls = [u for u in urls if "/p/" in u]
        logger.info(
            f"sitemap: {len(urls)} urls total, queued {len(product_urls)} products"
        )
        for url in product_urls:
            yield scrapy.Request(
                url,
                callback=self.parse_product,
                meta={"impersonate": self.IMPERSONATE_PROFILE},
                errback=self.errback,
            )

    def parse_product(self, response):
        product = self._extract_product(response)
        if not product:
            logger.warning(f"no Product JSON-LD found at {response.url}")
            return
        offer = product.get("offers") or {}
        if isinstance(offer, list):
            offer = offer[0] if offer else {}
        price = offer.get("price")
        name = product.get("name")
        if not (price and name):
            return
        brand = product.get("brand")
        if isinstance(brand, dict):
            brand = brand.get("name")
        yield {
            "product_id": str(product.get("sku") or product.get("@id") or response.url),
            "product_name": str(name).strip()[:500],
            "brand": brand,
            "category": None,
            "price": str(price),
            "currency": offer.get("priceCurrency") or self.currency,
            "available": "InStock" in str(offer.get("availability") or ""),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _extract_product(response):
        for raw in response.xpath(
            '//script[@type="application/ld+json"]/text()'
        ).getall():
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            candidates = (
                data.get("@graph")
                if isinstance(data, dict) and "@graph" in data
                else [data]
            )
            for c in candidates:
                if isinstance(c, dict) and c.get("@type") == "Product":
                    return c
        return None

    def errback(self, failure):
        logger.error(f"Request failed: {failure.request.url} — {failure.value!r}")

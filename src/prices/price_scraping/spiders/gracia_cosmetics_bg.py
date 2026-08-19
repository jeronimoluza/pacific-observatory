"""
Spider for Gracia Cosmetics (Bulgaria) — https://gracia-cosmetics.com/.

Custom PHP storefront, server-rendered. URL discovery via /sitemap.xml
(3,751 URLs, all product detail pages -- every entry ends in a numeric
`-<id>.html` suffix, no category/blog noise). Each PDP embeds a Schema.org
Product JSON-LD block (name, sku, category, offers.price/priceCurrency) --
no rendering needed. Confirmed live 2026-08-18: perfumes/cosmetics catalog,
prices in EUR (Bulgaria's site-declared currency; countries.yaml still lists
BGN as the country default -- the site's own priceCurrency wins per the
onboarding skill's currency rule). Country confirmed via the site's +359
(Bulgaria) contact number.

Sample: "Martin lion U 31 (EDP) Unisex parfum..." EUR 8.70.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_URL = "https://gracia-cosmetics.com/sitemap.xml"


class GraciaCosmeticsBgSpider(scrapy.Spider):
    name = "gracia_cosmetics_bg"
    allowed_domains = ["gracia-cosmetics.com"]
    currency = "EUR"
    language = "bg"

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

    async def start(self):
        yield scrapy.Request(
            _SITEMAP_URL, callback=self.parse_sitemap, errback=self.errback
        )

    def parse_sitemap(self, response):
        urls = response.xpath("//*[local-name()='loc']/text()").getall()
        logger.info(f"gracia_cosmetics_bg: sitemap has {len(urls)} product urls")
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product, errback=self.errback)

    def parse_product(self, response):
        product = self._extract_product(response)
        if not product:
            logger.warning(f"no Product JSON-LD found at {response.url}")
            return
        offers = product.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        name = product.get("name")
        price = offers.get("price")
        if not (name and price is not None):
            return
        category = product.get("category")
        if isinstance(category, dict):
            category = category.get("name")
        availability = str(offers.get("availability") or "")
        yield {
            "product_id": str(product.get("sku") or response.url),
            "product_name": str(name).strip()[:500],
            "category": category,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": "instock" in availability.lower() if availability else True,
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
        logger.error(
            f"gracia_cosmetics_bg request failed: {failure.request.url} — {failure.value!r}"
        )

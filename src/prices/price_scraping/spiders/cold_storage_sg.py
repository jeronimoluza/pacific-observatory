"""
Spider for Cold Storage Singapore - https://coldstorage.com.sg/
Sitemap-walker. PDP HTML is server-rendered (Next.js with SSR), exposing price
and name via stable CSS class prefixes (the hash suffix rotates per build):
  h1[class*="product-info__name"]   → product name
  [class*="product-price__price"]   → current price (S$X.XX); the
                                      __original variant is the struck-through
                                      pre-discount price, ignored.
Product id is the URL slug (only ~0.1% of URLs carry a trailing numeric id).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

SITEMAP_URL = "https://coldstorage.com.sg/sitemap_product.xml"
LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
PRICE_RE = re.compile(r"\$\s*([0-9]+\.[0-9]{2})")


class ColdStorageSgSpider(scrapy.Spider):
    name = "cold_storage_sg"
    allowed_domains = ["coldstorage.com.sg"]
    currency = "SGD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 8,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 4,
    }

    async def start(self):
        yield scrapy.Request(SITEMAP_URL, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = LOC_RE.findall(response.text)
        logger.info(f"cold_storage_sg: {len(urls)} product URLs in sitemap")
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        name = response.xpath(
            '//h1[contains(@class, "product-info__name")]/text()'
        ).get()
        if not name:
            name = response.xpath(
                '//h1[contains(@class, "product-name") or contains(@class, "ProductName")]/text()'
            ).get()
        if not name:
            logger.debug(f"no name found at {response.url}")
            return

        price_node = response.xpath(
            '//*[contains(@class, "product-price__price") '
            'and not(contains(@class, "original"))]/text()'
        ).get()
        if not price_node:
            price_node = response.xpath(
                '//*[contains(@class, "product-info__price") '
                'and not(contains(@class, "original"))]/text()'
            ).get()
        if not price_node:
            logger.debug(f"no price found at {response.url}")
            return

        m = PRICE_RE.search(price_node)
        if not m:
            return
        price = m.group(1)

        slug = response.url.rstrip("/").rsplit("/", 1)[-1]

        yield {
            "product_id": slug,
            "product_name": name.strip()[:500],
            "category": None,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

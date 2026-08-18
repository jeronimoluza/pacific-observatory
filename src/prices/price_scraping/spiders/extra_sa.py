"""
Spider for eXtra Stores Saudi Arabia (electronics/appliances) - extra.com

SAP Commerce Cloud (Hybris) storefront. Every PDP is server-rendered with a
schema.org Product JSON-LD block carrying name + sku + offers.price +
offers.priceCurrency; no Playwright, no impersonation needed. No `category`
field in the JSON-LD itself, so category is derived from the PDP's own URL
path segments (between the locale prefix and the trailing "/p/<sku>").

Seeded off /en-sa/sitemap.xml, which is a sitemap index pointing at ~50
"Product-en-SAR-N-*.xml" files (product PDPs) plus "Main-en-SAR-N-*.xml"
files (category/store-finder pages, skipped here).
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_INDEX = "https://www.extra.com/en-sa/sitemap.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_LDJSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>\s*(.*?)\s*</script>',
    re.DOTALL,
)


class ExtraSaSpider(scrapy.Spider):
    name = "extra_sa"
    allowed_domains = ["extra.com"]
    currency = "SAR"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP_INDEX, callback=self.parse_sitemap_index)

    def parse_sitemap_index(self, response):
        product_sitemaps = [
            u for u in _LOC_RE.findall(response.text) if "/Product-" in u
        ]
        logger.info("extra_sa: %d product sitemap files", len(product_sitemaps))
        for url in product_sitemaps:
            yield scrapy.Request(url, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = [u for u in _LOC_RE.findall(response.text) if "/p/" in u]
        logger.info("extra_sa: %d product URLs in %s", len(urls), response.url)
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        product = None
        for block in _LDJSON_RE.findall(response.text):
            data = self._loads(block)
            for node in self._iter_nodes(data):
                if isinstance(node, dict) and node.get("@type") == "Product":
                    product = node
                    break
            if product:
                break
        if not product:
            return

        offers = product.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = offers.get("price")
        name = product.get("name")
        if not name or price in (None, "", "0", "0.00"):
            return

        yield {
            "product_id": product.get("sku") or response.url,
            "product_name": str(name)[:500],
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "category": self._category(response.url),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _category(url):
        path = url.split("://", 1)[-1].split("/", 1)[-1]
        parts = path.split("/")
        # drop locale prefix (parts[0]) and trailing "p/<sku>"
        segments = [p for p in parts[1:-2] if p]
        return " > ".join(segments) if segments else None

    @staticmethod
    def _loads(block):
        try:
            return json.loads(block)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _iter_nodes(data):
        if isinstance(data, list):
            for d in data:
                yield d
        elif isinstance(data, dict):
            graph = data.get("@graph")
            if isinstance(graph, list):
                for d in graph:
                    yield d
            else:
                yield data

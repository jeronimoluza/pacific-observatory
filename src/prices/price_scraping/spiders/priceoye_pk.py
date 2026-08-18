"""
Spider for priceoye.pk — Pakistan electronics/mobile price-comparison
retailer.

Verified live 2026-08-17: priceoye.pk sells directly (not just a
price-comparison listing site) — each PDP embeds a schema.org Product
JSON-LD block server-side with a real `offers.price`/`priceCurrency`
(confirmed "Infinix Note 60 Edge 5G" -> PKR 87399.00, InStock), same
pattern as jarir_sa/btech_eg. robots.txt (ROBOTSTXT_OBEY=False repo-wide)
points at https://priceoye.pk/sitemap/sitemap-index.xml ->
sitemap-product.xml, 15,911 product URLs
(https://priceoye.pk/<category>/<brand>/<slug>), so this walks that
sitemap directly rather than guessing category pages (the homepage/
category listing HTML does not embed per-product prices — only
descriptive price-range text and an Elasticsearch "similar products"
widget with no price field).
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP = "https://priceoye.pk/sitemap/sitemap-product.xml"
_LOC_RE = re.compile(r"<loc>(https://priceoye\.pk/[^<]+)</loc>")
_LDJSON_RE = re.compile(
    r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
    re.DOTALL,
)


class PriceoyePkSpider(scrapy.Spider):
    name = "priceoye_pk"
    allowed_domains = ["priceoye.pk"]
    currency = "PKR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 32,
        "DOWNLOAD_DELAY": 0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = sorted(set(_LOC_RE.findall(response.text)))
        logger.info("priceoye_pk: %d product URLs in sitemap", len(urls))
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        product = None
        for block in _LDJSON_RE.findall(response.text):
            data = self._loads(block)
            if isinstance(data, dict) and data.get("@type") == "Product":
                product = data
                break

        if not product:
            return

        offers = product.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = offers.get("price")
        name = product.get("name")
        if not name or price in (None, "", 0, "0"):
            return

        yield {
            "product_id": product.get("productID") or response.url.rsplit("/", 1)[-1],
            "product_name": str(name).strip()[:500],
            "category": product.get("category"),
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": str(offers.get("availability", "")).endswith("InStock"),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _loads(block):
        try:
            return json.loads(block)
        except (ValueError, TypeError):
            return None

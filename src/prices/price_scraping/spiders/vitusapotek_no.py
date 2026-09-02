"""
Vitusapotek (Norwegian pharmacy chain), https://www.vitusapotek.no/.

Next.js SSR storefront. No open product-search API found (the category
listing's above-the-fold "recently viewed" widget is a client-hydrated
skeleton, but the main product grid below it IS server-rendered), and the
site publishes a product sitemap at
https://www.vitusapotek.no/sitemap/sitemap-product-1.xml (15,400 PDP URLs,
one page -- page 2 -> 404, confirmed live 2026-08-31). Each in-stock PDP
embeds a schema.org Product JSON-LD block server-side with a clean Offer
(price/priceCurrency/availability); sample verified: 'Nordic Grip Walking
brodder str 37-41 1 par' sku 951820 -> NOK 239.90, InStock. Prescription-
only medicine PDPs (under /reseptbelagte-legemidler/) carry no Product
JSON-LD at all (no public price), so those rows are silently skipped by
the parser -- no special-casing needed. A sibling BreadcrumbList JSON-LD's
second-to-last entry is the leaf category. product_id is the schema `sku`
(numeric, matches the URL's trailing id).
"""

import html
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_URL = "https://www.vitusapotek.no/sitemap/sitemap-product-1.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_LDJSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>\s*(.*?)\s*</script>',
    re.DOTALL,
)


class VitusapotekNoSpider(scrapy.Spider):
    name = "vitusapotek_no"
    allowed_domains = ["vitusapotek.no"]
    currency = "NOK"
    language = "no"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 16,
        "DOWNLOAD_DELAY": 0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP_URL, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = _LOC_RE.findall(response.text)
        logger.info("vitusapotek_no: %d product URLs in sitemap", len(urls))
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        product = None
        breadcrumb = None
        for block in _LDJSON_RE.findall(response.text):
            data = self._loads(block)
            if not isinstance(data, dict):
                continue
            if data.get("@type") == "Product":
                product = data
            elif data.get("@type") == "BreadcrumbList":
                breadcrumb = data

        if not product:
            return  # e.g. prescription-only medicine PDPs carry no price

        offers = product.get("offers") or {}
        price = offers.get("price")
        name = product.get("name")
        sku = product.get("sku")
        if not name or not sku or price in (None, "", 0, "0"):
            return

        category = None
        if breadcrumb:
            items = breadcrumb.get("itemListElement") or []
            if len(items) >= 2:
                leaf = items[-2]
                category = leaf.get("name") if isinstance(leaf, dict) else None

        yield {
            "product_id": str(sku),
            "product_name": html.unescape(str(name)).strip()[:500],
            "category": html.unescape(str(category)) if category else None,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": str(offers.get("availability", "")).endswith("InStock"),
            "url": offers.get("url") or response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _loads(block):
        try:
            return json.loads(block)
        except (ValueError, TypeError):
            return None

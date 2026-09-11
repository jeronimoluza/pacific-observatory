"""SPAR2U (Botswana) — SPAR Group's online grocery storefront.

Custom Next.js-ish platform, not WooCommerce/Shopify/PrestaShop/OpenCart.
No open product-list API found; the product sitemap
(/sitemaps/products/sitemap-products-1.xml, 8,370 URLs) is the enumerable
surface. Each PDP embeds a JSON-LD Product node with an AggregateOffer:
`lowPrice` is always the literal placeholder "0.00" across every product
sampled (bug/placeholder on the tenant's side, not a real price), while
`highPrice` carries the real single-store price (offerCount is always 1).
So this spider reads highPrice, not lowPrice/price.

Currency confirmed from the payload itself (priceCurrency: BWP), matching
countries.yaml's BWP default for Botswana but read from the site, not assumed.
Page family: PDP only (sitemap -> PDP, no listing page ever fetched).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S | re.I)
_JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.S | re.I,
)


class Spar2uBwSpider(scrapy.Spider):
    name = "spar2u_bw"
    allowed_domains = ["spar2u.co.bw", "www.spar2u.co.bw"]
    SITEMAP_URL = "https://www.spar2u.co.bw/sitemaps/products/sitemap-products-1.xml"
    currency = "BWP"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(self.SITEMAP_URL, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        locs = _LOC_RE.findall(response.text)
        product_urls = [u for u in locs if "/product/" in u]
        logger.info(f"{self.name} sitemap urls={len(locs)} products={len(product_urls)}")
        for url in product_urls:
            yield scrapy.Request(url, callback=self.parse_product)

    @staticmethod
    def _iter_nodes(data):
        if isinstance(data, list):
            for item in data:
                yield from Spar2uBwSpider._iter_nodes(item)
        elif isinstance(data, dict):
            yield data
            graph = data.get("@graph")
            if isinstance(graph, list):
                for item in graph:
                    yield from Spar2uBwSpider._iter_nodes(item)

    def parse_product(self, response):
        for block in _JSONLD_RE.findall(response.text):
            try:
                data = json.loads(block)
            except (json.JSONDecodeError, TypeError):
                continue
            for node in self._iter_nodes(data):
                if not isinstance(node, dict) or node.get("@type") != "Product":
                    continue
                name = node.get("name")
                offers = node.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                price = offers.get("highPrice") or offers.get("price")
                currency = offers.get("priceCurrency") or self.currency
                if not name or not price:
                    continue
                try:
                    if float(price) == 0:
                        continue
                except (TypeError, ValueError):
                    continue
                cats = node.get("category") or []
                cat_names = [
                    c.get("name") for c in cats if isinstance(c, dict) and c.get("name")
                ]
                yield {
                    "product_id": str(node.get("sku") or ""),
                    "product_name": str(name).strip()[:500],
                    "category": " > ".join(cat_names) if cat_names else None,
                    "price": str(price),
                    "currency": currency,
                    "available": True,
                    "url": response.url,
                    "language": self.language,
                    "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
                }
                return

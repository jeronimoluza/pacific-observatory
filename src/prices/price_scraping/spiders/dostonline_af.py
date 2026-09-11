"""
Dost Online Store (Afghanistan) -- a Kabul-based electronics/mobile retailer
(dostonlinestore.com). No Shopify/WooCommerce/etc fingerprint; site is a
custom-built storefront with a standard XML sitemap and schema.org
Product/Offer JSON-LD on every product-detail page.

Verified live 2026-09-11: https://dostonlinestore.com/sitemap.xml lists 215
URLs, 193 of them /products/<slug> -- a real catalog, not a small fixed set.
Each PDP embeds clean JSON-LD, e.g. for /products/galaxy-s24-ultra-256gb:
{"@type":"Product","name":"...","sku":"...","category":"Mobile",
 "offers":{"@type":"Offer","priceCurrency":"AFN","price":38396,...}}
-- native AFN pricing (not USD), and the page's own description text
explicitly targets Kabul/Afghanistan ("قیمت روز و خرید آنلاین ... در کابل و
سراسر افغانستان" = "today's price and online purchase ... in Kabul and
across Afghanistan"), confirming this is a domestic retailer, not a
diaspora remittance/gifting service (contrast with kharid.af / yaganchiz.com,
both USD-priced or diaspora-audience sites rejected in the same wave).

This spider walks the sitemap once, filters to /products/ URLs, then
requests each PDP and extracts the JSON-LD Product node. No pagination API
exists -- the sitemap URL count is a static one-shot list of the current
catalog; CLOSESPIDER_ITEMCOUNT (the pipeline's --max-items) governs how many
PDPs are actually fetched per run.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP = "https://dostonlinestore.com/sitemap.xml"
_LDJSON_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I
)


class DostonlineAfSpider(scrapy.Spider):
    name = "dostonline_af"
    allowed_domains = ["dostonlinestore.com"]
    currency = "AFN"
    language = "fa"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = re.findall(r"<loc>([^<]+)</loc>", response.text)
        product_urls = [u for u in urls if "/products/" in u]
        logger.info("dostonline_af: %d product urls in sitemap", len(product_urls))
        for u in product_urls:
            yield scrapy.Request(u, callback=self.parse_product)

    def parse_product(self, response):
        for block in _LDJSON_RE.findall(response.text):
            try:
                data = json.loads(block)
            except (json.JSONDecodeError, ValueError):
                continue
            if data.get("@type") != "Product":
                continue
            offers = data.get("offers") or {}
            price = offers.get("price")
            if price is None:
                continue
            try:
                if float(price) == 0:
                    continue
            except (TypeError, ValueError):
                continue
            name = (data.get("name") or "").strip()
            if not name:
                continue
            availability = offers.get("availability") or ""
            yield {
                "product_id": str(data.get("sku") or response.url),
                "product_name": name[:500],
                "category": data.get("category"),
                "price": str(price),
                "currency": offers.get("priceCurrency") or self.currency,
                "available": "InStock" in availability or availability == "",
                "url": offers.get("url") or response.url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            return

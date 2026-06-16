"""
Spider for Tops Online (Thailand) - https://www.tops.co.th/

The site is Next.js with server-side rendering behind Cloudflare. Plain Scrapy
HTML requests succeed (the standard CF page is the "Just a moment..." challenge
which Tops does NOT use — direct requests work).

Sitemap-index lists per-language product sitemaps; we walk the English ones
(~50K SKUs in sitemap.en-products-1.xml plus a tail in en-products-2.xml).
Each PDP exposes `__NEXT_DATA__` with `props.pageProps.productData` carrying
sku (barcode), name, price (THB), brand, and category. No JSON-LD Product
schema, so we parse the Next-state blob directly.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

SITEMAP_INDEX = "https://www.tops.co.th/sitemap/sitemap-index.xml"
LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)


class TopsThSpider(scrapy.Spider):
    name = "tops_th"
    allowed_domains = ["tops.co.th"]
    currency = "THB"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 8,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 4,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(SITEMAP_INDEX, callback=self.parse_index)

    def parse_index(self, response):
        for loc in LOC_RE.findall(response.text):
            if "en-products" in loc:
                yield scrapy.Request(loc, callback=self.parse_product_sitemap)

    def parse_product_sitemap(self, response):
        urls = LOC_RE.findall(response.text)
        logger.info(f"tops_th: {len(urls)} product URLs in {response.url}")
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        body = response.text
        m = NEXT_DATA_RE.search(body)
        if not m:
            return
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            return

        product = data.get("props", {}).get("pageProps", {}).get("productData")
        if not isinstance(product, dict):
            return

        sku = product.get("sku") or product.get("barcode") or product.get("productId")
        name = product.get("name") or product.get("productName")
        price = product.get("price")
        if price is None:
            price = product.get("finalPrice") or product.get("displayPrice")
        if not (sku and name and price is not None):
            return

        category = self._extract_category(data.get("props", {}).get("pageProps", {}))

        yield {
            "product_id": str(sku),
            "product_name": str(name).strip()[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": product.get("inStock", True),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def _extract_category(self, page_props: dict) -> str | None:
        cat = page_props.get("categoryData")
        if isinstance(cat, dict):
            for key in ("name", "categoryName", "title"):
                v = cat.get(key)
                if isinstance(v, str) and v.strip():
                    return v.strip()
        return None

"""
Spider for btech.com — Egypt electronics/appliance retailer.

Custom SSR storefront (redirects / -> /ar). robots.txt points at
https://btech.com/sitemap.xml, an 11MB sitemap mixing category (/ar/c/...)
and product (/ar/p/<slug>) URLs; 7,206 product URLs found. Each PDP embeds a
schema.org Product JSON-LD block server-side with sku/name/offers
(priceCurrency/price/availability), confirmed live 2026-08-17: 'ماوس سبيد
لينك كابا' -> EGP 295, InStock. A sibling BreadcrumbList JSON-LD gives the
category path (second-to-last entry is the leaf category; last is the
product itself) — same pattern as jarir_kw/4sough_af. Category listing pages
render no inline product data (client-side XHR), so this spider walks the
sitemap's product URLs directly rather than crawling categories.

Re-verified live 2026-08-17: GET /sitemap.xml -> 200, 7,206 <loc>
https://btech.com/ar/p/... entries. GET one PDP -> 200, ~72KB gzip / 391KB
decoded — much lighter than 4sough's PDPs, full sitemap crawl is feasible
inside the collect-run time budget.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP = "https://btech.com/sitemap.xml"
_LOC_RE = re.compile(r"<loc>(https://btech\.com/ar/p/[^<]+)</loc>")
_LDJSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>\s*(.*?)\s*</script>',
    re.DOTALL,
)


class BtechEgSpider(scrapy.Spider):
    name = "btech_eg"
    allowed_domains = ["btech.com"]
    currency = "EGP"
    language = "ar"

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
        logger.info("btech_eg: %d product URLs in sitemap", len(urls))
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
            return

        offers = product.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = offers.get("price")
        name = product.get("name")
        if not name or price in (None, "", 0, "0"):
            return

        category = None
        if breadcrumb:
            items = breadcrumb.get("itemListElement") or []
            if len(items) >= 2:
                leaf = items[-2]
                category = leaf.get("name") or (leaf.get("item") or {}).get("name")
                if category:
                    category = category.strip()

        yield {
            "product_id": product.get("sku") or response.url.rsplit("/", 1)[-1],
            "product_name": str(name).strip()[:500],
            "category": category,
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

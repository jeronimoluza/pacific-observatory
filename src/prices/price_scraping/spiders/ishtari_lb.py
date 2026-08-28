"""
Spider for Ishtari.com (Lebanon) -- https://www.ishtari.com/.

Next.js pages-router SSR general-merchandise store. `ishtari.com` 301s to
`www.ishtari.com`. robots.txt confirms crawlable `/product/` and `/category/`
paths and points at a real sitemap index:
https://sitemap.ishtari.com/sitemap.xml -> 13 `products<N>.xml` child
sitemaps (plus sellers.xml/manufacturers.xml/categories.xml/information.xml,
filtered out — spider only follows children whose URL contains "/products"),
~3000 <loc> entries each (~39k products total). Each PDP's single ld+json
script tag holds a JSON *array* of entities (Product, BreadcrumbList,
MerchantReturnPolicy, OfferShippingDetails) rather than one script per
entity, so parsing must flatten list-typed blocks before filtering on
@type=="Product" — confirmed live 2026-08-17 on
/distinctive-fan-shaped-pattern-tpu-skin/p=9413 -> USD 0.5, InStock, sku
"max5813", real Offer (USD price, priceCurrency, availability). Sibling
BreadcrumbList JSON-LD is present but shallow (Home -> product name only,
no intermediate category), so category is left None.

Re-verified live 2026-08-17: GET https://sitemap.ishtari.com/sitemap.xml ->
200, 17 child sitemaps (13 product-bearing). GET one child sitemap -> 200,
3000 <loc> entries. GET one PDP -> 200, 41KB, real USD price in ld+json
Offer.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_INDEX = "https://sitemap.ishtari.com/sitemap.xml"
# 13 product sitemaps x ~3000 URLs = ~39k products; capped to stay inside
# the ~25-minute collect-run budget. Bench 2026-08-17 (full run, cap=2000):
# 2014 requests in 274s (~7.35 req/s at CONCURRENT_REQUESTS_PER_DOMAIN=16),
# so 8000 is ~18min, leaving headroom under the 25min budget.
_MAX_PRODUCTS = 8000
_SITEMAP_LOC_RE = re.compile(r"<loc>\s*([^<\s][^<]*?)\s*</loc>")
_LDJSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>\s*(.*?)\s*</script>',
    re.DOTALL,
)


class IshtariLbSpider(scrapy.Spider):
    name = "ishtari_lb"
    allowed_domains = ["ishtari.com", "sitemap.ishtari.com", "www.ishtari.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 16,
        "DOWNLOAD_DELAY": 0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._scheduled = 0

    async def start(self):
        yield scrapy.Request(_SITEMAP_INDEX, callback=self.parse_sitemap_index)

    def parse_sitemap_index(self, response):
        children = [
            loc for loc in _SITEMAP_LOC_RE.findall(response.text) if "/products" in loc
        ]
        logger.info("ishtari_lb: %d product child sitemaps", len(children))
        for loc in children:
            yield scrapy.Request(loc, callback=self.parse_product_sitemap)

    def parse_product_sitemap(self, response):
        urls = _SITEMAP_LOC_RE.findall(response.text)
        for url in urls:
            if self._scheduled >= _MAX_PRODUCTS:
                return
            self._scheduled += 1
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        product = None
        for block in _LDJSON_RE.findall(response.text):
            data = self._loads(block)
            candidates = data if isinstance(data, list) else [data]
            for entry in candidates:
                if isinstance(entry, dict) and entry.get("@type") == "Product":
                    product = entry
                    break
            if product:
                break
        if not product:
            return

        offers = product.get("offers") or {}
        price = offers.get("price")
        name = product.get("name")
        if not name or price in (None, "", 0, "0"):
            return

        yield {
            "product_id": str(product.get("sku") or response.url.rsplit("=", 1)[-1]),
            "product_name": str(name).strip()[:500],
            "category": None,
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

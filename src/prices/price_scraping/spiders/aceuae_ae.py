"""
Spider for aceuae.com — Al-Futtaim ACE hardware/home-living retailer, UAE.

Custom Next.js storefront. curl_cffi chrome124 impersonation clears the TSPD
(F5) loader stub that bare requests see on category pages (that stub is a
defensive script tag, not a hard block). Category pages themselves render no
inline product data client-side (Next.js RSC streaming payload with no price
field), so this spider walks the product sitemap directly instead --
matches the pattern already shipped for btech_eg / 4sough_af.

robots.txt -> Sitemap: https://www.aceuae.com/sitemap/sitemap-ae.xml (a real
sitemap index; open, unblocked, no ClaudeBot/anthropic-ai disallow). That
index lists per-category-tree sub-sitemaps split by locale and content type;
sitemap-ae-hardware-en-products.xml alone carries 11,591 distinct
/en/products/<slug>/<id> URLs (2026-08-17) -- a real, large, walkable
catalog, not a homepage carousel.

Each PDP embeds a clean schema.org Product JSON-LD block server-side (name,
sku, category, priceCurrency, price, availability), confirmed live: "O Cedar
ProMist MAX Microfiber Sponge Mop Refill (23 cm)" -> AED 2.00, sku 2144175.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_INDEX = "https://www.aceuae.com/sitemap/sitemap-ae.xml"
_PRODUCT_SITEMAP_RE = re.compile(r"<loc>([^<]*-en-products\.xml)</loc>")
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_LDJSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>\s*(.*?)\s*</script>',
    re.DOTALL,
)


class AceuaeAeSpider(scrapy.Spider):
    name = "aceuae_ae"
    allowed_domains = ["aceuae.com"]
    currency = "AED"
    language = "en"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
        "DOWNLOAD_DELAY": 0.2,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 4,
    }
    IMPERSONATE_PROFILE = "chrome124"

    async def start(self):
        yield scrapy.Request(
            _SITEMAP_INDEX,
            callback=self.parse_index,
            meta={"impersonate": self.IMPERSONATE_PROFILE},
        )

    def parse_index(self, response):
        for loc in _PRODUCT_SITEMAP_RE.findall(response.text):
            yield scrapy.Request(
                loc,
                callback=self.parse_product_sitemap,
                meta={"impersonate": self.IMPERSONATE_PROFILE},
            )

    def parse_product_sitemap(self, response):
        urls = sorted(set(_LOC_RE.findall(response.text)))
        logger.info(f"aceuae_ae: {len(urls)} product URLs in {response.url}")
        for url in urls:
            yield scrapy.Request(
                url,
                callback=self.parse_product,
                meta={"impersonate": self.IMPERSONATE_PROFILE},
            )

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
            "product_id": product.get("sku")
            or response.url.rstrip("/").rsplit("/", 1)[-1],
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

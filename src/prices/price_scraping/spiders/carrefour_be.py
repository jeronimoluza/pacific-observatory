"""
Spider for Carrefour Belgium -- https://www.carrefour.be/.

Salesforce Commerce Cloud (Demandware) storefront -- confirmed by the
`/on/demandware.store/Sites-carrefour-be-Site/default/...` URLs embedded in
the homepage (store-selector, checkout-shipping endpoints). No WAF/CDN
challenge on the front page or on PDPs (server: cloudflare, but a plain GET
clears at 200 with curl_cffi impersonate="chrome124" and even with a bare
User-Agent). `Search-UpdateGrid?cgid=...` ignores unknown category ids and
falls back to a fixed 72-item grid, so it is NOT usable for category
enumeration -- but `/sitemap_index.xml` -> `/nl/sitemap_0.xml` (and
sitemap_1..4) lists ~100k direct PDP URLs (nl and fr duplicates of the same
SKU), so this walks the sitemap PDP list directly, same pattern as
ecofamily_hu.

Each PDP carries a `schema.org/Product` JSON-LD block (name, sku, price,
priceCurrency). Sample verified live: "Brie Coeur de Lion Kaas", EUR 6.25,
sku 00080032. Only `/nl/` PDP urls are walked (fr duplicates the same SKUs
under a different slug/URL and would double-count the catalog).
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_INDEX = "https://www.carrefour.be/sitemap_index.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_LD_JSON_RE = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
_PDP_STRIDE = 5  # sample every Nth PDP to keep the crawl bounded


class CarrefourBeSpider(scrapy.Spider):
    name = "carrefour_be"
    allowed_domains = ["carrefour.be"]
    currency = "EUR"
    language = "nl"

    IMPERSONATE_PROFILE = "chrome124"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            _SITEMAP_INDEX,
            callback=self.parse_sitemap_index,
            meta={"impersonate": self.IMPERSONATE_PROFILE},
        )

    def parse_sitemap_index(self, response):
        shards = _LOC_RE.findall(response.text)
        logger.info("carrefour_be: %d sitemap shards", len(shards))
        for shard in shards:
            yield scrapy.Request(
                shard,
                callback=self.parse_sitemap_shard,
                meta={"impersonate": self.IMPERSONATE_PROFILE},
            )

    def parse_sitemap_shard(self, response):
        locs = _LOC_RE.findall(response.text)
        product_urls = [loc for loc in locs if "/nl/" in loc and loc.endswith(".html")]
        sampled = product_urls[::_PDP_STRIDE]
        logger.info(
            "carrefour_be: sampled %d/%d nl PDP urls from %s",
            len(sampled), len(product_urls), response.url,
        )
        for url in sampled:
            yield scrapy.Request(
                url,
                callback=self.parse_product,
                meta={"impersonate": self.IMPERSONATE_PROFILE},
            )

    def parse_product(self, response):
        product = None
        for block in _LD_JSON_RE.findall(response.text):
            try:
                data = json.loads(block)
            except (ValueError, TypeError):
                continue
            if data.get("@type") == "Product":
                product = data
                break

        if not product:
            logger.warning("carrefour_be: no Product JSON-LD on %s", response.url)
            return

        offers = product.get("offers") or {}
        price = offers.get("price")
        name = product.get("name")
        if not name or price in (None, "", 0):
            return

        yield {
            "product_id": product.get("sku") or product.get("mpn") or response.url,
            "product_name": str(name).strip()[:500],
            "category": None,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": "InStock" in (offers.get("availability") or ""),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

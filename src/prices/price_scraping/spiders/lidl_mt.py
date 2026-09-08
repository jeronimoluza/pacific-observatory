"""
Spider for Lidl Malta -- https://www.lidl.com.mt/.

Same storefront platform as lidl.ie and lidl.sk (see known_blockers.md) --
but unlike lidl.ie (where sampled PDPs mostly carry NO price field at
all), Malta's PDPs consistently carry a real EUR price in their
schema.org/Product JSON-LD, even though `availability` is always
"InStoreOnly" (this is Lidl's rotating weekly-offer leaflet mirrored as
PDP pages, not a delivery storefront -- same shape as many already-
onboarded leaflet/promo sources).

`/static/sitemap.xml` -> `/p/export/MT/en/product_sitemap.xml.gz` lists
458 PDP urls (small, rotating range). Verified live 2026-09-06: 5/5
sampled PDPs had a real price, e.g. "Orvieto Classico DOP", EUR 3.79.
"""

import gzip
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_INDEX = "https://www.lidl.com.mt/static/sitemap.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_LD_JSON_RE = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S)


class LidlMtSpider(scrapy.Spider):
    name = "lidl_mt"
    allowed_domains = ["lidl.com.mt"]
    currency = "EUR"
    language = "en"

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
        product_shards = [s for s in shards if "product_sitemap" in s]
        logger.info("lidl_mt: %d product-sitemap shards", len(product_shards))
        for shard in product_shards:
            yield scrapy.Request(
                shard,
                callback=self.parse_sitemap_shard,
                meta={"impersonate": self.IMPERSONATE_PROFILE},
            )

    def parse_sitemap_shard(self, response):
        try:
            xml_text = gzip.decompress(response.body).decode("utf-8")
        except OSError:
            xml_text = response.text
        product_urls = _LOC_RE.findall(xml_text)
        logger.info("lidl_mt: %d PDP urls from %s", len(product_urls), response.url)
        for url in product_urls:
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
            if isinstance(data, dict) and data.get("@type") == "Product":
                product = data
                break

        if not product:
            return

        offers = product.get("offers") or []
        if isinstance(offers, dict):
            offers = [offers]
        offer = offers[0] if offers else {}
        price = offer.get("price")
        name = product.get("name")
        if not name or price in (None, "", 0):
            return

        yield {
            "product_id": product.get("sku") or str(product.get("gtin13") or response.url),
            "product_name": str(name).strip()[:500],
            "category": None,
            "price": str(price),
            "currency": offer.get("priceCurrency") or self.currency,
            "available": "InStock" in str(offer.get("availability") or ""),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

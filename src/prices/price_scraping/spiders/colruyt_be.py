"""
Spider for Colruyt Belgium -- https://www.colruyt.be/ via its online grocery
storefront https://www.collectandgo.be/.

colruyt.be itself is a corporate/brand site (React/Vue widgets, no product
data) that links out to collectandgo.be ("Collect&Go"), Colruyt's real
click-and-collect online supermarket. `/sitemap.xml` on collectandgo.be
lists dedicated product sitemaps (`sitemap-nl_BE-product-{1,2,3}.xml.gz`,
~5k urls each, plus `fr_FR` duplicates). Each PDP carries a
`schema.org/Product` JSON-LD block with a real EUR price -- no anti-bot,
plain curl_cffi clears at 200. Verified live 2026-09-06: "CAMPINA Halfvol
Brik 1L", EUR 1.45. Spider walks the `nl_BE` product shards only (fr_FR
duplicates the same catalog under a different locale).
"""

import gzip
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_INDEX = "https://www.collectandgo.be/sitemap.xml"
_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
_LD_JSON_RE = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
_PDP_STRIDE = 15  # sample every Nth PDP across ~15k nl_BE PDPs (3 x 5k)


class ColruytBeSpider(scrapy.Spider):
    name = "colruyt_be"
    allowed_domains = ["collectandgo.be"]
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
        product_shards = [s for s in shards if "nl_BE-product" in s]
        logger.info("colruyt_be: %d nl_BE product-sitemap shards", len(product_shards))
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
        product_urls = [u.strip() for u in _LOC_RE.findall(xml_text)]
        sampled = product_urls[::_PDP_STRIDE]
        logger.info(
            "colruyt_be: sampled %d/%d PDP urls from %s",
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
        if not name or price in (None, "", 0):
            return

        yield {
            "product_id": product.get("sku") or product.get("gtin13") or response.url,
            "product_name": str(name).strip()[:500],
            "category": None,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": "InStock" in str(offers.get("availability") or ""),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

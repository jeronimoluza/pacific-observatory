"""
Spider for De Prati (Ecuador) -- www.deprati.com.ec.

SAP Commerce Cloud (Hybris) storefront. Bare curl gets a Cloudflare
"Attention Required" 403; curl_cffi impersonate=chrome124 clears it on both
the homepage and PDPs.

Enumerability: https://www.deprati.com.ec/sitemap.xml is a real sitemap
index that includes ~22 `Product-es-USD-<n>-<hash>.xml` shards (the `<hash>`
context param is a signed token, so this spider re-discovers the shard URLs
from sitemap.xml on every run rather than hardcoding them). Each shard is a
urlset of ~1,024 real `/p/<slug>/p/<code>` PDP urls -- verified live
2026-08-17 on shard 0.

Ecuador is dollarized (USD) but the SAP Hybris storefront formats prices
with EU-style separators (comma decimal, period thousands -- e.g.
"$1.939,00"). This spider does NOT parse that formatted string: each PDP
embeds a `:rawproduct='{...}'` Vue attribute with a clean `price.value`
float and `price.currencyIso` ("USD") already resolved server-side, so the
EU-separator trap in `formattedValue` is sidestepped entirely.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_INDEX = "https://www.deprati.com.ec/sitemap.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_PRODUCT_SHARD_RE = re.compile(r"/medias/Product-es-USD-\d+-")
_RAWPRODUCT_RE = re.compile(r"rawproduct='(\{.*?\})'", re.DOTALL)

_MAX_SHARDS = 6
_PRODUCTS_PER_SHARD = 200


class DepratiEcSpider(scrapy.Spider):
    name = "deprati_ec"
    allowed_domains = ["deprati.com.ec"]
    currency = "USD"
    language = "es"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }
    IMPERSONATE_PROFILE = "chrome124"

    async def start(self):
        yield scrapy.Request(
            _SITEMAP_INDEX,
            callback=self.parse_index,
            meta={"impersonate": self.IMPERSONATE_PROFILE},
        )

    def parse_index(self, response):
        shard_urls = [
            loc
            for loc in _LOC_RE.findall(response.text)
            if _PRODUCT_SHARD_RE.search(loc)
        ][:_MAX_SHARDS]
        logger.info("deprati_ec: %d product shards selected", len(shard_urls))
        for shard_url in shard_urls:
            yield scrapy.Request(
                shard_url,
                callback=self.parse_shard,
                meta={"impersonate": self.IMPERSONATE_PROFILE},
            )

    def parse_shard(self, response):
        urls = _LOC_RE.findall(response.text)[:_PRODUCTS_PER_SHARD]
        logger.info("deprati_ec: %s -> %d product urls", response.url, len(urls))
        for url in urls:
            yield scrapy.Request(
                url,
                callback=self.parse_product,
                meta={"impersonate": self.IMPERSONATE_PROFILE},
            )

    def parse_product(self, response):
        m = _RAWPRODUCT_RE.search(response.text)
        if not m:
            return
        try:
            product = json.loads(m.group(1))
        except ValueError:
            return

        name = product.get("name")
        code = product.get("code")
        price = product.get("price") or {}
        value = price.get("value")
        currency = price.get("currencyIso")
        if not name or not code or value is None or currency != self.currency:
            return

        stock = product.get("stock") or {}
        status = (stock.get("stockLevelStatus") or {}).get("code")

        yield {
            "product_id": str(code),
            "product_name": str(name)[:500],
            "category": None,
            "price": str(value),
            "currency": currency,
            "available": status != "outOfStock",
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

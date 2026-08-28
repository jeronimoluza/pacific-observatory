"""
Spider for Katapulk (Cuba diaspora remittance/marketplace) -- https://www.katapulk.com/.

Ships to Cuba, priced in USD for the sending (non-Cuban) buyer -- this is a
diaspora-priced USD signal, NOT a domestic Cuban retail price in CUP.

The Angular Universal SSR shell serves zero structured price data on product
pages. The real catalog is enumerable via /sitemap.xml, which lists every
live /cu/products/<slug> PDP (254 URLs, live-checked 2026-08-17). Each slug
is then resolved to price/name/currency via the api-services.katapulk.com
Catalog/Search/ProductDetails JSON endpoint (curl_cffi chrome124; bare HTTP
gets an Angular shell with no data).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP = "https://www.katapulk.com/sitemap.xml"
_DETAIL = (
    "https://api-services.katapulk.com/api/v2/Catalog/Search/ProductDetails"
    "?slug={slug}&zoneId=undefined&municipalityId=undefined&Currency=USD"
)
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_PRODUCT_RE = re.compile(r"/cu/products/([a-z0-9-]+)$")


class KatapulkCuSpider(scrapy.Spider):
    name = "katapulk_cu"
    allowed_domains = ["katapulk.com", "www.katapulk.com", "api-services.katapulk.com"]
    currency = "USD"
    language = "es"

    custom_settings = {
        "IMPERSONATE_BROWSERS": ["chrome124"],
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            _SITEMAP, callback=self.parse_sitemap, meta={"impersonate": "chrome124"}
        )

    def parse_sitemap(self, response):
        slugs = set()
        for loc in _LOC_RE.findall(response.text):
            m = _PRODUCT_RE.search(loc)
            if m:
                slugs.add(m.group(1))
        logger.info(f"katapulk_cu: {len(slugs)} product slugs in sitemap")
        for slug in slugs:
            yield scrapy.Request(
                _DETAIL.format(slug=slug),
                callback=self.parse_product,
                meta={"impersonate": "chrome124", "slug": slug},
            )

    def parse_product(self, response):
        try:
            body = response.json()
        except ValueError:
            logger.warning(
                f"katapulk_cu: non-JSON response for {response.meta['slug']}"
            )
            return
        data = body.get("data") or {}
        name = (data.get("name") or "").strip()
        variants = data.get("variants") or []
        if not name or not variants:
            return
        variant = variants[0]
        price = variant.get("displayDefaultPrice")
        if not price:
            return
        slug = response.meta["slug"]
        yield {
            "product_id": str(data.get("objectID") or variant.get("id") or slug),
            "product_name": name[:500],
            "category": (data.get("store") or {}).get("name"),
            "price": str(price),
            "currency": data.get("currency") or self.currency,
            "available": not variant.get("isOutStock", False),
            "url": f"https://www.katapulk.com/cu/products/{slug}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

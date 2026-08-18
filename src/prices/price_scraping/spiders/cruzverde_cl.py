"""
Cruz Verde (Chile) - https://www.cruzverde.cl

Angular SPA; www.cruzverde.cl always serves the SPA shell regardless of path
(no server-rendered catalog). Real data lives on a separate host,
api.cruzverde.cl, which 401s with INVALID_SESSION on an anonymous product
call - the fix is a guest-session login first
(POST https://api.cruzverde.cl/customer-service/login with an empty JSON
body, 201, sets an auth cookie), then
GET https://api.cruzverde.cl/product-service/products/detail/{id} 200s.
No TLS impersonation needed for either host (plain requests/Scrapy clears
both).

Product-id universe comes from the site's own sitemap
(sitemap_{0,1,2}-product.xml, ~12.6k URLs total, id is the numeric segment
before ".html"). Prices are CLP - confirmed via the detail response's own
`priceCurrency` field.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_LOGIN_URL = "https://api.cruzverde.cl/customer-service/login"
_DETAIL_URL = "https://api.cruzverde.cl/product-service/products/detail/{}"
_SITEMAPS = [
    "https://www.cruzverde.cl/sitemap_0-product.xml",
    "https://www.cruzverde.cl/sitemap_1-product.xml",
    "https://www.cruzverde.cl/sitemap_2-product.xml",
]
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_ID_RE = re.compile(r"/(\d+)\.html$")


class CruzverdeClSpider(scrapy.Spider):
    name = "cruzverde_cl"
    allowed_domains = ["cruzverde.cl"]
    currency = "CLP"
    language = "es"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(
            _LOGIN_URL,
            method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps({}),
            callback=self.parse_login,
        )

    def parse_login(self, response):
        if response.status != 201:
            logger.error("cruzverde_cl: guest login failed status=%s", response.status)
            return
        logger.info("cruzverde_cl: guest session established")
        for url in _SITEMAPS:
            yield scrapy.Request(url, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = {}
        for loc in _LOC_RE.findall(response.text):
            m = _ID_RE.search(loc)
            if m:
                urls[m.group(1)] = loc
        logger.info("cruzverde_cl: %s product ids in %s", len(urls), response.url)
        for pid, page_url in urls.items():
            yield scrapy.Request(
                _DETAIL_URL.format(pid),
                callback=self.parse_detail,
                meta={"product_id": pid, "page_url": page_url},
            )

    def parse_detail(self, response):
        if response.status != 200:
            return
        try:
            payload = response.json()
        except ValueError:
            return
        data = payload.get("productData") or {}
        name = data.get("name")
        price = data.get("price")
        if not name or not price:
            return
        yield {
            "product_id": response.meta["product_id"],
            "product_name": name.strip()[:500],
            "category": data.get("category"),
            "price": str(price),
            "currency": data.get("priceCurrency") or self.currency,
            "available": True,
            "url": response.meta["page_url"],
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

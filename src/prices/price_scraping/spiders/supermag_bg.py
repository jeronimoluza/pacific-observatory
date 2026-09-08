"""
Spider for Supermag Bulgaria -- https://www.supermag.bg/.

Legacy jQuery storefront (Sofia office-supply-oriented online supermarket).
Category listing pages ship a `Loading` spinner placeholder and hydrate via
AJAX. Playwright network trace found the backend:
`GET /hash/products/index?type=products_list&nid=<category_id>` -- but
passing an unrecognised/omitted `nid` does NOT error, it falls back to the
FULL catalog in one response (no auth, no pagination needed). Verified
live 2026-09-06: 1,938 products in one ~1.3MB JSON response, e.g. "Кисело
Мляко Вереа 2% 400 г", BGN 1.89.

Spider hits the endpoint once (no nid) and yields every product directly --
no crawling/pagination required.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_PRODUCTS_URL = "https://www.supermag.bg/hash/products/index?type=products_list"


class SupermagBgSpider(scrapy.Spider):
    name = "supermag_bg"
    allowed_domains = ["supermag.bg"]
    currency = "BGN"
    language = "bg"

    IMPERSONATE_PROFILE = "chrome124"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
        },
        "DOWNLOAD_TIMEOUT": 60,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(
            _PRODUCTS_URL,
            callback=self.parse_products,
            meta={"impersonate": self.IMPERSONATE_PROFILE},
        )

    def parse_products(self, response):
        try:
            data = response.json()
        except Exception:
            logger.warning("supermag_bg: non-JSON response")
            return

        products = data.get("products") or []
        logger.info("supermag_bg: %d products in catalog dump", len(products))
        for p in products:
            price = p.get("price")
            name = p.get("title")
            if not name or price in (None, "", 0):
                continue
            uri = p.get("uri") or ""
            yield {
                "product_id": str(p.get("id")),
                "product_name": str(name).strip()[:500],
                "category": p.get("node_title"),
                "price": str(price),
                "currency": self.currency,
                "available": bool(p.get("is_available")),
                "url": f"https://www.supermag.bg{uri}" if uri else response.url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

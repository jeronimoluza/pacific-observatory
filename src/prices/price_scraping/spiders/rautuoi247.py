"""
Spider for Rau Tuoi 247 (rautuoi247.vn) - Vietnam fresh produce/meat/fish
online grocer (HCMC), built on the Sapo/Bizweb storefront platform.

Sapo exposes a Shopify-style JSON catalog endpoint at /products.json, no
auth required. Paginates via ?page=N&limit=50 until a short page confirms
exhaustion.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://rautuoi247.vn"
_API = _BASE + "/products.json"
_PAGE_LIMIT = 50


class Rautuoi247Spider(scrapy.Spider):
    name = "rautuoi247"
    allowed_domains = ["rautuoi247.vn"]
    currency = "VND"
    language = "vi"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    async def start(self):
        yield self._page_request(page=1)

    def _page_request(self, page):
        return scrapy.Request(
            f"{_API}?page={page}&limit={_PAGE_LIMIT}",
            callback=self.parse_page,
            meta={"page": page},
            headers={"Accept": "application/json"},
        )

    def parse_page(self, response):
        page = response.meta["page"]
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("rautuoi247: non-JSON response p%d", page)
            return

        products = payload.get("products") or []
        if not products:
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            product_name = p.get("name")
            url_path = p.get("url")
            category = p.get("product_type") or None
            if not product_name or not url_path:
                continue
            url = (
                f"{_BASE}{url_path}"
                if url_path.startswith("/")
                else f"{_BASE}/{url_path}"
            )

            for v in p.get("variants") or []:
                price = v.get("price")
                if price is None:
                    continue
                yield {
                    "product_id": v.get("sku") or v.get("barcode") or str(v.get("id")),
                    "product_name": product_name,
                    "price": price,
                    "currency": self.currency,
                    "category": category,
                    "url": f"{url}?variant={v.get('id')}" if url else None,
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                }

        yield self._page_request(page=page + 1)

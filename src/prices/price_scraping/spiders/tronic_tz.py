"""
Tronic / Cash Sale Stores Limited (Tanzania) — https://www.tronic.co.tz/.

Shopify storefront; reads the public /products.json feed directly.
Electrical fittings, LED lighting and household electrical hardware
catalogue, prices in TZS (confirmed via /meta.json: country "TZ",
currency "TZS", myshopify_domain "tronic-tanzania.myshopify.com").

Verified live 2026-09-28: GET /products.json?limit=5 -> 200, real priced
items ("20W LED Surface Ceiling Light" TZS 9,000.00, "TRONIC 24W LED
Panel Light" TZS 30,000.00). Page 2 returns a fully distinct set
("24W Spot LED Downlight" TZS 30,000.00 etc.), confirming enumeration
past page 1.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.tronic.co.tz"
_API = _BASE + "/products.json"
_PAGE_LIMIT = 250


class TronicTzSpider(scrapy.Spider):
    name = "tronic_tz"
    allowed_domains = ["tronic.co.tz"]
    currency = "TZS"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2.0,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_MAX_DELAY": 30.0,
        "RETRY_TIMES": 8,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504, 408],
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
            logger.error("tronic_tz: non-JSON response p%d", page)
            return

        products = payload.get("products") or []
        if not products:
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            handle = p.get("handle")
            product_id = str(p.get("id", ""))
            product_name = p.get("title")
            category = p.get("product_type") or None
            url = f"{_BASE}/products/{handle}" if handle else None
            if not product_name or not url:
                continue
            for v in p.get("variants") or []:
                price = v.get("price")
                if price is None:
                    continue
                try:
                    if float(price) <= 0:
                        continue
                except (TypeError, ValueError):
                    continue
                variant_label = v.get("option1", "")
                full_name = (
                    f"{product_name} - {variant_label}"
                    if variant_label and variant_label.lower() != "default title"
                    else product_name
                )
                yield {
                    "product_id": v.get("sku")
                    or v.get("barcode")
                    or f"{product_id}_{v.get('id')}",
                    "product_name": full_name,
                    "price": price,
                    "currency": self.currency,
                    "category": category,
                    "url": f"{url}?variant={v.get('id')}" if url else None,
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                }

        yield self._page_request(page=page + 1)

    def errback(self, failure):
        logger.error(
            "tronic_tz: request failed %s — %r",
            failure.request.url,
            failure.value,
        )

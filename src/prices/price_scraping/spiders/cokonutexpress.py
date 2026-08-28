"""Cokonut Express -- https://www.cokonutexpress.com/.

Asian/Pacific specialty grocer (Japanese, Filipino, and Pacific-islander
snacks and staples) shipping to Guam AND CNMI (also serves Saipan) from
Burien, WA. Squarespace commerce store; the /products collection page
exposes the full catalog as JSON at ?format=json -- no auth, no pagination
observed (~57 items on the single response). Each item's own
`structuredContent.priceMoney` is always 0.00 -- the real price lives on
`structuredContent.variants[*].priceMoney`; rows with a zero/blank variant
price are skipped."""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_URL = "https://www.cokonutexpress.com/products?format=json"


class CokonutExpressSpider(scrapy.Spider):
    name = "cokonutexpress"
    allowed_domains = ["cokonutexpress.com", "www.cokonutexpress.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2.0,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_URL, callback=self.parse_items)

    def parse_items(self, response):
        try:
            payload = response.json()
        except ValueError:
            logger.warning("cokonutexpress: non-JSON response at %s", response.url)
            return
        items = payload.get("items") or []
        logger.info("cokonutexpress: %d items", len(items))
        scraped_at = datetime.now(timezone.utc).isoformat()
        for it in items:
            sc = it.get("structuredContent") or {}
            variants = sc.get("variants") or []
            name = (it.get("title") or "").strip()
            url = response.urljoin(it.get("fullUrl") or "")
            if not name or not variants:
                continue
            for v in variants:
                price_money = v.get("priceMoney") or {}
                price = price_money.get("value")
                try:
                    price_f = float(price) if price is not None else 0.0
                except (TypeError, ValueError):
                    price_f = 0.0
                if price_f <= 0:
                    continue
                attrs = v.get("attributes") or {}
                label = " / ".join(str(x) for x in attrs.values() if x)
                vname = f"{name} ({label})" if label else name
                yield {
                    "product_id": v.get("sku") or it.get("id"),
                    "product_name": vname[:500],
                    "price": str(price_f),
                    "currency": price_money.get("currency") or self.currency,
                    "category": None,
                    "url": url,
                    "scraped_at": scraped_at,
                }

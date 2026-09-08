"""
Spider for e-khumaisa.com -- "E-khumaisa Express Market", Niamey, Niger.

`e-khumaisa.com` itself does NOT resolve in DNS (confirmed against 8.8.8.8
and 1.1.1.1, no A/AAAA/CNAME record) despite being cited as the storefront
URL in the business's own social media (TikTok, Instagram, Facebook). The
real storefront runs on the "Take App" West-African e-commerce SaaS
platform at `https://take.app/ekhumaisaexpressmarke` -- found via WebSearch
after the bare domain failed to resolve (the "search for the real domain"
recovery pattern).

The storefront page itself is a Next.js app that renders NO product data
server-side (only i18n label strings and store metadata are embedded in
the RSC payload) -- confirmed by grepping the raw HTML for `"price"` /
`XOF` occurrences, which only surface in unrelated UI-copy strings. A
Playwright network-capture of a category page surfaced the real backend:

    GET https://take.app/api/stores/<storeId>/products/recommendation

`<storeId>` = `cmj5wh1u9000j04johrttdmtc` for this store (visible in every
`take.app/api/app/storeId/<id>/...` request the page fires; also embedded,
JSON-escaped, in the homepage's RSC payload as `"id":"cmj5wh1u9000j04johrttdmtc"`
paired with `"alias":"ekhumaisaexpressmarke"`).

Despite the "recommendation" name, this endpoint returns the WHOLE
catalog, not a curated rail: verified live 2026-09-06, 485 distinct
products in one unpaginated call (tripods, rice, cosmetics, phone
accessories -- a wide cross-COICOP catalog, not a themed "recommended for
you" subset). Prices are plain XOF integers (no minor-unit division
needed -- e.g. "Riz Basmati Danu 1kg" = 1650 XOF matches the displayed
price).
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_STORE_ID = "cmj5wh1u9000j04johrttdmtc"
_API = f"https://take.app/api/stores/{_STORE_ID}/products/recommendation"
_BASE = "https://take.app/ekhumaisaexpressmarke"


class EkhumaisaNeSpider(scrapy.Spider):
    name = "ekhumaisa_ne"
    allowed_domains = ["take.app"]
    currency = "XOF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DOWNLOAD_TIMEOUT": 60,
    }

    async def start(self):
        yield scrapy.Request(_API, callback=self.parse_products)

    def parse_products(self, response):
        try:
            rows = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON response from {_API}")
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for row in rows:
            if row.get("visibility") != "VISIBLE" or row.get("soldout"):
                continue
            product_id = row.get("id")
            name = row.get("name")
            price = row.get("price")
            if not (product_id and name and price):
                continue
            n += 1
            yield {
                "product_id": str(product_id),
                "product_name": str(name).strip()[:500],
                "category": None,
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}/p/{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"{self.name}: {n} rows from {len(rows)} raw catalog entries")

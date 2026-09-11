"""
Spider for DS Super Mart — dssupermart.com, "Fresh Grocery Store -
Sri Lanka".

Not a WooCommerce/Shopify storefront -- homepage is a thin static
shell; Playwright network trace found the real catalog at a plain
in-house PHP endpoint: /grocery/api/products.php?limit=N, no auth,
returns the WHOLE catalog in one call (confirmed 666 products, no
pagination needed at limit=1000).

This reads as a raw POS-system export rather than a curated online
catalog -- names are informal/abbreviated Sinhala-English POS entries
("Kiri The 400g" = Kothmale-brand milk tea, "Kothmale Yorget 5in1" =
yogurt) and the mix includes non-food POS items (mobile reload cards,
stationery, batteries) alongside real grocery products. Still real
LKR retail prices for a real Sri Lankan convenience store.
channel: convenience.

No stable per-product URL exists in the payload (id + name only) --
DuplicationPipeline dedups on item["url"], so the spider synthesizes
`?id=<id>` on the API endpoint itself as a unique per-row URL.

Page family: API only — the spider never fetches an HTML page.

Verified live 2026-09-11: --max-items 100 run against the API
produced rows. Sample: "Manchi Wafer Chocolate 400g" LKR 550.00,
"Salsa Biscuits" LKR 50.00.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE = "https://dssupermart.com/grocery/api/products.php"


class DssupermartLkSpider(scrapy.Spider):
    name = "dssupermart_lk"
    allowed_domains = ["dssupermart.com"]
    currency = "LKR"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(f"{BASE}?limit=1000", callback=self.parse)

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        try:
            payload = response.json()
        except ValueError:
            logger.warning(f"dssupermart_lk: non-JSON response at {response.url}")
            return
        products = ((payload.get("data") or {}).get("products")) or []
        logger.info(f"dssupermart_lk: {len(products)} products")
        for p in products:
            if p.get("status") != "in_stock":
                continue
            name = (p.get("name") or "").strip()
            price = p.get("sell_price")
            pid = p.get("id")
            if not (name and price and pid):
                continue
            try:
                price = float(price)
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            yield {
                "product_id": str(pid),
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": p.get("category_name"),
                "url": f"{BASE}?id={pid}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

"""
Spider for Mahajana Super — mahajanaonline.com (mirrored 1:1 at
shopmahajana.com, same title/content -- treated as one tenant, only
mahajanaonline.com onboarded), "Shop Fresh Groceries at Mahajana Super
– Kandy & Gampola".

Not WooCommerce/Shopify -- runs on the "TakeApp" social-commerce
storefront builder (media CDN is storage.googleapis.com/takeapp/...).
Playwright network trace found the real catalog at:

    /api/stores/<store_id>/products/recommendation

(store_id = clr1lr70v004t2k8xe0u7h4qr for this tenant) -- despite the
"/recommendation" name this returns the store's actual product list
(141 items spanning Fresh Fruits, ice cream, rice, baby items), not a
small curated subset. No pagination parameter found; treated as the
whole reachable catalog for now.

Prices are integers with no explicit minor-unit field in the payload;
inferred as cents from magnitude (confirmed against category context:
"Green Grapes" 29000 -> LKR 290.00 for a 0.1kg unit is a plausible
imported-fruit price, "Taj Mahal Fiesta Basmathi Rice 5Kg+1Kg Free"
800000 -> LKR 8,000.00 is a plausible bulk imported-rice bundle price;
taking the values as whole rupees would be absurd at both ends).

Page family: API only — the spider never fetches an HTML page.

Verified live 2026-09-11: --max-items 100 run against the API
produced rows. Sample: "Green Grapes" LKR 290.00, "Velona Cuddles
Moisturising Baby Lotion 100ml" LKR 399.00 (non-food, correctly still
emitted -- COICOP routing happens downstream in the classifier).
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

STORE_ID = "clr1lr70v004t2k8xe0u7h4qr"
URL = f"https://mahajanaonline.com/api/stores/{STORE_ID}/products/recommendation"


class MahajanasuperLkSpider(scrapy.Spider):
    name = "mahajanasuper_lk"
    allowed_domains = ["mahajanaonline.com"]
    currency = "LKR"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(URL, callback=self.parse)

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        try:
            products = response.json()
        except ValueError:
            logger.warning(f"mahajanasuper_lk: non-JSON response at {response.url}")
            return
        if not isinstance(products, list):
            return
        logger.info(f"mahajanasuper_lk: {len(products)} products")
        for p in products:
            if p.get("soldout"):
                continue
            name = (p.get("name") or "").strip()
            pid = p.get("id")
            price = p.get("price")
            if not (name and pid and price):
                continue
            try:
                price_val = float(price) / 100.0
            except (TypeError, ValueError):
                continue
            if price_val <= 0:
                continue
            cats = p.get("categories") or []
            cat = " > ".join(c.get("name") for c in cats if c.get("name")) or None
            yield {
                "product_id": str(pid),
                "product_name": name,
                "price": price_val,
                "currency": self.currency,
                "category": cat,
                "url": f"{URL}#{pid}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

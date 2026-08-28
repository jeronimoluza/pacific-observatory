"""
Spider for Metro Online (METRO Pakistan) — https://www.metro-online.pk/.

Public JSON API, no auth, no WAF (Xcentric-backend Node.js). One request
fetches the full category tree, then one request per leaf category returns
that category's whole product list in a single response (no pagination
observed — the 136-product "Milk" category came back in one call).

GET admin.metro-online.pk/api/read/Categories?&filter=storeId&filterValue=10
-> {"data": [...]}, 236 categories, `category_assortment_type` in
{"Food","Non-Food"}; the category's own `id` field is the `tier2Id` used
to filter products (verified: category id=8353 "Milk" -> product
tier2Id=8353). We walk every `id` where category_assortment_type=="Food"
(183 of 236, re-verified live 2026-08-06).

GET admin.metro-online.pk/api/read/Products?filter=tier2Id&filterValue=<id>&storeId=10
-> {"data": [...]}. `price` is the listed/original price; `sell_price` is
the actual current selling price when set (falls back to `price`
otherwise). Sample: 'Nurpur Milk 1.5L x8' price=4100, sell_price=2700 PKR.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_CATEGORIES_URL = (
    "https://admin.metro-online.pk/api/read/Categories?&filter=storeId&filterValue=10"
)
_PRODUCTS_URL = (
    "https://admin.metro-online.pk/api/read/Products"
    "?filter=tier2Id&filterValue={cat_id}&storeId=10"
)


class MetroPkSpider(scrapy.Spider):
    name = "metro_pk"
    allowed_domains = ["metro-online.pk"]
    currency = "PKR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_CATEGORIES_URL, callback=self.parse_categories)

    def parse_categories(self, response):
        try:
            payload = response.json()
        except ValueError:
            logger.error("metro_pk: non-JSON at Categories endpoint")
            return
        categories = payload.get("data") or []
        food = [c for c in categories if c.get("category_assortment_type") == "Food"]
        logger.info(
            f"metro_pk: {len(food)} food categories to walk (of {len(categories)})"
        )
        for cat in food:
            cat_id = cat.get("id")
            if cat_id is None:
                continue
            yield scrapy.Request(
                _PRODUCTS_URL.format(cat_id=cat_id),
                callback=self.parse_products,
                meta={"category_name": cat.get("category_name")},
            )

    def parse_products(self, response):
        try:
            payload = response.json()
        except ValueError:
            logger.warning(f"metro_pk: non-JSON at {response.url}")
            return
        products = payload.get("data") or []
        category = response.meta["category_name"]
        logger.info(f"metro_pk: {category} products={len(products)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            item = self._item(p, category, scraped_at)
            if item:
                yield item

    def _item(self, p, category, scraped_at):
        name = p.get("product_name")
        price = p.get("sell_price") or p.get("price")
        if not name or not price:
            return None
        return {
            "product_id": str(p.get("id") or p.get("product_code_app") or ""),
            "product_name": name.strip()[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": bool(p.get("active", True)),
            "url": p.get("deep_link") or "https://www.metro-online.pk/",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

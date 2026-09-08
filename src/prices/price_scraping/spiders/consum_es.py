"""
Spider for Consum (Spain) — https://tienda.consum.es/.

Valencian supermarket cooperative; regional coverage the national chains
miss (shard AI_NOTES). Storefront is an Angular SPA on the "TOL" platform
(cdn-consum.aktiosdigitalservices.com), but the product/category endpoints
are a public JSON API with no auth required:

  GET /api/rest/V1.0/shopping/category/menu
      -> full category tree, each node has id/nombre/subcategories[]
         (recurse to leaves; ~661 leaf ids re-verified live 2026-09-06)

  GET /api/rest/V1.0/catalog/product?page=1&limit=50&offset=0
      &categories=<leaf_id>&includeFilters=false
      -> {"totalCount":N,"hasMore":bool,"products":[...]}
         each product: code, ean, productData.name, productData.url,
         priceData.prices[] (id="PRICE" -> value.centAmount is the actual
         EUR unit price despite the field name -- NOT cents; id
         ="OFFER_PRICE" is a temporary discount, only used if present and
         cheaper than PRICE), priceData.unitPriceUnitType (per-kg/per-l
         reference, not charged).

Re-verified live 2026-09-06 (via Playwright network trace to find the
endpoint, then confirmed the exact same JSON returns from a cold
curl_cffi GET with no cookies): leaf id 1970 (Frutos secos) -> 200,
totalCount 301, sample product "Palomitas Microondas Saladas Pack de 3"
code 7064835, PRICE value.centAmount 2.49, OFFER_PRICE 1.99.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://tienda.consum.es/api/rest/V1.0"
_PAGE_LIMIT = 50
MAX_PAGES_PER_CATEGORY = 20  # safety cap; most leaf categories are <300 items


class ConsumEsSpider(scrapy.Spider):
    name = "consum_es"
    allowed_domains = ["tienda.consum.es"]
    currency = "EUR"
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(
            f"{_BASE}/shopping/category/menu", callback=self.parse_menu
        )

    def parse_menu(self, response):
        try:
            tree = response.json()
        except ValueError:
            logger.error("consum_es: non-JSON at /shopping/category/menu")
            return
        leaf_ids = set()

        def walk(nodes):
            for node in nodes or []:
                subs = node.get("subcategories") or []
                if subs:
                    walk(subs)
                elif node.get("id"):
                    leaf_ids.add(node["id"])

        walk(tree)
        logger.info(f"consum_es: {len(leaf_ids)} leaf categories to walk")
        for cat_id in leaf_ids:
            yield scrapy.Request(
                f"{_BASE}/catalog/product?page=1&limit={_PAGE_LIMIT}&offset=0"
                f"&categories={cat_id}&includeFilters=false",
                callback=self.parse_category,
                meta={"category": cat_id, "page": 1},
            )

    def parse_category(self, response):
        cat_id = response.meta["category"]
        page = response.meta["page"]
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"consum_es: non-JSON for category={cat_id} page={page}")
            return
        products = data.get("products") or []
        logger.info(f"consum_es: category={cat_id} page={page} count={len(products)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            pdata = p.get("productData") or {}
            price_data = p.get("priceData") or {}
            prices = {pr.get("id"): pr for pr in (price_data.get("prices") or [])}
            price_entry = prices.get("OFFER_PRICE") or prices.get("PRICE")
            if not price_entry:
                continue
            price = (price_entry.get("value") or {}).get("centAmount")
            name = pdata.get("name")
            if price is None or not name:
                continue
            yield {
                "product_id": p.get("code"),
                "product_name": name.strip()[:500],
                "category": str(cat_id),
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": pdata.get("url"),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        if data.get("hasMore") and page < MAX_PAGES_PER_CATEGORY:
            nxt = page + 1
            offset = (nxt - 1) * _PAGE_LIMIT
            yield scrapy.Request(
                f"{_BASE}/catalog/product?page={nxt}&limit={_PAGE_LIMIT}"
                f"&offset={offset}&categories={cat_id}&includeFilters=false",
                callback=self.parse_category,
                meta={"category": cat_id, "page": nxt},
            )

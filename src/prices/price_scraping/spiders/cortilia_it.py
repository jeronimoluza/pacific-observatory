"""
Spider for Cortilia (Italy) -- https://www.cortilia.it/.

Farm-to-table online grocer, Next.js storefront. The homepage/category pages
themselves are client-routed (a category slug like /di-stagione 404s when
fetched directly and carries no product data in __NEXT_DATA__) but a
Playwright network trace (2026-09-06) found the real backend, which is a
clean JSON REST API needing no auth, session, or address/CAP selection:

  GET https://api.cortilia.it/store-api/v1/catalog/{catalog}/aisles
      -> {"aisles": [{"id", "name", "categories": [{"id","name"}, ...]}]}

  GET https://api.cortilia.it/store-api/v1/catalog/{catalog}/aisles/{aisleId}/categories/{categoryId}
      -> {"listing": {"productcount", "productstoshow", "products": [...]}}
      (confirmed: productstoshow == productcount even above 200 -- e.g.
      "essenziali" returned all 278 of 278 in a single call, no pagination
      needed)

The default catalog (delivery zone) is "catalog_cassina" -- confirmed live
2026-09-06 that this default resolves without any address/zip input, so no
CAP-gate workaround is needed (unlike carrefour.it / hemkop.se on this same
onboarding pass).

15 aisles x ~9 categories each = 140 aisle/category pairs; the same product
commonly appears in more than one aisle (e.g. "in-evidenza" is a curated
cross-cut), so results are deduped by product id across the whole crawl.

Each product carries one or more `variants` (pack sizes); one row is emitted
per variant since price and pack size differ.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_CATALOG = "catalog_cassina"
_BASE = "https://api.cortilia.it/store-api/v1"
_AISLES_URL = f"{_BASE}/catalog/{_CATALOG}/aisles"


class CortiliaItSpider(scrapy.Spider):
    name = "cortilia_it"
    allowed_domains = ["cortilia.it"]
    currency = "EUR"
    language = "it"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {"Referer": "https://www.cortilia.it/"},
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_variant_ids = set()

    async def start(self):
        yield scrapy.Request(_AISLES_URL, callback=self.parse_aisles)

    def parse_aisles(self, response):
        try:
            data = response.json()
        except ValueError:
            return
        aisles = data.get("aisles") or []
        logger.info(f"cortilia_it: {len(aisles)} aisles")
        for aisle in aisles:
            aisle_id = aisle.get("id")
            for cat in aisle.get("categories") or []:
                cat_id = cat.get("id")
                if not aisle_id or not cat_id:
                    continue
                url = f"{_BASE}/catalog/{_CATALOG}/aisles/{aisle_id}/categories/{cat_id}"
                yield scrapy.Request(
                    url,
                    callback=self.parse_category,
                    meta={"aisle_id": aisle_id, "cat_id": cat_id},
                )

    def parse_category(self, response):
        try:
            data = response.json()
        except ValueError:
            return
        listing = data.get("listing") or {}
        products = listing.get("products") or []
        cat_id = response.meta["cat_id"]
        logger.info(f"cortilia_it: cat={cat_id} products={len(products)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for prod in products:
            pid = prod.get("id")
            name = (prod.get("name") or "").strip()
            category = prod.get("category") or cat_id
            urlify = prod.get("urlify") or ""
            for variant in prod.get("variants") or []:
                vid = variant.get("id")
                if not vid or vid in self._seen_variant_ids:
                    continue
                price_obj = variant.get("price") or {}
                price = price_obj.get("sale") or price_obj.get("list")
                if price is None:
                    continue
                try:
                    price_val = float(price)
                except (TypeError, ValueError):
                    continue
                if price_val <= 0:
                    continue
                self._seen_variant_ids.add(vid)
                pack = variant.get("name") or ""
                full_name = f"{name} {pack}".strip()
                yield {
                    "product_id": vid,
                    "product_name": full_name[:500],
                    "category": category,
                    "price": price_val,
                    "currency": self.currency,
                    "available": bool(prod.get("available", True)),
                    "url": f"https://www.cortilia.it/prodotto/{pid}/{urlify}",
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                }

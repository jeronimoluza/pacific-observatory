"""
Glotelho (Cameroon) — https://glotelho.cm/.

Cameroon's largest first-party online retailer (own SKU codes, own
showrooms, Adobe-Commerce/Magento 2 catalogue behind a Nuxt storefront).
Broad, non-grocery-led assortment -- so `channel: dept-store` per the
GLOSSARY test -- but it carries two genuine top-level food-and-beverage
departments, which is what this spider walks:

    supermarche-1266   "Supermarché"  -- grocery shelf (rice, oil, sauces,
                                        tinned fish, breakfast packs, plus
                                        some household/hygiene lines)
    la-cave-1351       "La Cave"      -- drinks: soft drinks, juices, beer,
                                        wine and spirits (COICOP 02.1)

DISCOVERY (Playwright network trace, 2026-09-05): the Nuxt front end talks
to TWO different backends on the same page load --

  1. https://site.glotelho.cm/rest/fr/V1/products?searchCriteria[...]
     Magento 2 REST, and it DOES require `Authorization: Bearer <token>`
     (a static integration token baked into the storefront).
  2. https://glotelho.cm/api/v1/products/category   <-- what this spider uses
     The storefront's OWN same-origin BFF endpoint. POST JSON, **no auth of
     any kind**, no cookie, no CSRF -- only `content-type: application/json`
     and `x-locale: fr`. It proxies (1) and returns the identical Magento
     product objects.

Using (2) means the spider never carries a bearer token that could be
rotated out from under it.

    POST https://glotelho.cm/api/v1/products/category
    {"categoryId": "1266", "attributes": [], "pageNumber": N,
     "pageSize": 100, "sort": "created_at"}
    -> {"success": true,
        "data": {"items": [...], "search_criteria": {...},
                 "total_count": 359}}

`total_count` is authoritative and pageNumber paginates cleanly -- page 1
and page 2 at pageSize=100 were verified to share ZERO ids, so this is a
real paginating catalogue and not a re-served fixed page (the Magento
short-page trap in known_blockers.md).

Verified live 2026-09-05:
    category 1266 -> total_count 359
    category 1351 -> total_count 439
Samples: "Whisky Monkey Shoulder – 40% alc – 100 cl" 30612 XAF,
"Riz parfumé Africana 5 kg + 5 sardines Piment&eacute;es Africana (125 g)"
6987 XAF, "Boisson énergisante - X-ray energy drink - 50 cl" 875 XAF.

The two categories OVERLAP (the whisky above carries category_links for
both 1266 and 1351), so the spider de-duplicates on Magento product id
across categories before yielding.

CURRENCY: XAF, matching countries.yaml. Magento `price` here is a plain
decimal in major units (875 / 6987 / 30612 FCFA all check out against the
rendered page) -- no minor-unit divide, unlike WooCommerce's Store API.

Page family parsed: **API** (this spider never fetches a browsable page).
The `url` emitted is the customer-facing PDP built from the Magento
`url_key`/`sku`, which the spider does not itself request.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://glotelho.cm"
API_URL = f"{BASE_URL}/api/v1/products/category"

# Top-level food-and-beverage departments. Everything else on Glotelho is
# electronics / appliances / fashion / books.
CATEGORIES = {
    "1266": "Supermarché",
    "1351": "La Cave",
}

PAGE_SIZE = 100
MAX_PAGES = 40  # safety cap: 4,000 products per category

HEADERS = {
    "accept": "application/json",
    "content-type": "application/json",
    "x-locale": "fr",
    "origin": BASE_URL,
    "referer": f"{BASE_URL}/",
}


class GlotelhoCmSpider(scrapy.Spider):
    name = "glotelho_cm"
    allowed_domains = ["glotelho.cm"]
    currency = "XAF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_ids: set[str] = set()

    async def start(self):
        for cat_id in CATEGORIES:
            yield self._api_request(cat_id, 1)

    def _api_request(self, cat_id: str, page: int) -> scrapy.Request:
        body = {
            "categoryId": str(cat_id),
            "attributes": [],
            "pageNumber": page,
            "pageSize": PAGE_SIZE,
            "sort": "created_at",
        }
        return scrapy.Request(
            API_URL,
            method="POST",
            headers=HEADERS,
            body=json.dumps(body),
            callback=self.parse_page,
            errback=self.errback,
            meta={"cat_id": str(cat_id), "page": page},
            dont_filter=True,
        )

    def errback(self, failure):
        logger.warning(f"{self.name}: request failed -- {failure.value!r}")

    def parse_page(self, response):
        cat_id = response.meta["cat_id"]
        page = response.meta["page"]
        try:
            payload = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON response at page {page} cat {cat_id}")
            return

        data = payload.get("data") or {}
        items = data.get("items") or []
        total = data.get("total_count")

        scraped_at = datetime.now(timezone.utc).isoformat()
        yielded = 0
        for item in items:
            pid = item.get("id")
            if pid is None:
                continue
            pid = str(pid)
            if pid in self._seen_ids:
                continue

            price = item.get("price")
            if price is None:
                # Magento `bundle`/`configurable` rows can omit a top-level
                # price; there is no shelf price to emit for those.
                continue
            try:
                price_f = float(price)
            except (TypeError, ValueError):
                continue
            if price_f <= 0:
                continue

            name = (item.get("name") or "").strip()
            if not name:
                continue

            self._seen_ids.add(pid)
            yielded += 1

            url_key = self._attr(item, "url_key")
            sku = item.get("sku")
            url = (
                f"{BASE_URL}/product/{url_key}-{pid}"
                if url_key
                else f"{BASE_URL}/product/{pid}"
            )

            yield {
                "product_id": sku or pid,
                "product_name": name[:500],
                "category": CATEGORIES[cat_id],
                "price": str(price),
                "currency": self.currency,
                "available": bool(
                    (item.get("extension_attributes") or {})
                    .get("stock_item", {})
                    .get("is_in_stock", True)
                ),
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        logger.info(
            f"{self.name}: cat={cat_id} page={page} items={len(items)} "
            f"yielded={yielded} total_count={total}"
        )

        if items and len(items) >= PAGE_SIZE and page < MAX_PAGES:
            if total is None or page * PAGE_SIZE < int(total):
                yield self._api_request(cat_id, page + 1)

    @staticmethod
    def _attr(item: dict, code: str):
        for a in item.get("custom_attributes") or []:
            if a.get("attribute_code") == code:
                return a.get("value")
        return None

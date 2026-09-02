"""
Cerise (Gabon) — https://cerise.ga/.

Grocery storefront built on the "Jiffy" white-label quick-commerce platform
(formerly The Cloud Retail / Native Commerce; the same SaaS also powers
CircleK, Vilo, Ocado-branded and other tenants worldwide). The storefront is
a client-rendered SPA (Vite bundle at /assets/index-*.js) with no product
data in the raw HTML response body except an SSR `window.__INITIAL_STATE__`
preview — so this walks the platform's real JSON API instead of the page.

Reverse-engineered from the bundle's minified `U.catalog` route map and the
`OC` (Cerise) tenant-config object embedded at build time:

    company id (x-company-id header): d93a174a-d1f7-4504-97d5-c075dd86d0f0
    warehouse code:                    CERIS
    API host:                          https://api2.jiffygrocery.co.uk

Requests need `x-company-id` (there is no per-request auth token for
anonymous browsing) plus `warehouseCode` on every call, else the API 400s
with COMPANY_ID_IS_MISSING.

Walk:
  1. GET /catalog/v1/client/categories/tree?warehouseCode=CERIS
     -> full category tree (135 nodes / 72 leaves as probed 2026-08-31),
     mixing food departments (Fruits & Légumes, Boulangerie, Crèmerie,
     Viandes, Épicerie, Boissons, Petit-Déjeuner...) with non-food
     (Hygiène, Électroménager, Loisirs).
  2. For every leaf category id, GET
     /catalog/v2/tree/categories/{id}?warehouseCode=CERIS
     -> {"data": {"category": {"products": [...]}}}. This is the ONLY
     endpoint tried that returns more than the first page (the
     `/catalog/v1/client/categories/{id}/products` route the SPA's own
     pagination helper (`El`/`getProductsPaged`) targets is a 422 on any
     `page`/`pageNumber`/`offset` query param the bundle's own filter
     builder would send — the pager appears to be driven by an internal
     cursor the client never needs to name explicitly for the first
     screen, and passing any of the three plausible names either 422s or
     is silently ignored (pagination.current stays 1, identical ids
     returned) — see brief trap #7. The v2 tree endpoint returns a larger,
     un-paginated slice per leaf (measured 49 of a reported total=79 on
     leaf 2124) with no further param needed, so leaves are the unit of
     pagination instead of an in-category cursor.

Prices are integers stored at an internal x100 scale regardless of the
tenant's real currency_minor_unit (XAF has none) — confirmed against the
SSR-rendered display price for product 75593 (raw 200000 -> "FCFA 2,000"
on the page) — so every price here is divided by 100.

Product ids: the platform's own SKU code (e.g. "CERIS7134789806") from the
first offer, falling back to the numeric product id.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://cerise.ga"
API_BASE = "https://api2.jiffygrocery.co.uk"
COMPANY_ID = "d93a174a-d1f7-4504-97d5-c075dd86d0f0"
WAREHOUSE_CODE = "CERIS"


class CeriseGaSpider(scrapy.Spider):
    name = "cerise_ga"
    allowed_domains = ["cerise.ga", "api2.jiffygrocery.co.uk"]
    currency = "XAF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def _headers(self):
        return {
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/",
            "x-company-id": COMPANY_ID,
            "Accept": "application/json",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_product_ids: set[int] = set()
        self.leaf_count = 0

    async def start(self):
        yield scrapy.Request(
            f"{API_BASE}/catalog/v1/client/categories/tree?warehouseCode={WAREHOUSE_CODE}",
            headers=self._headers(),
            callback=self.parse_tree,
            errback=self.errback,
        )

    def parse_tree(self, response):
        try:
            nodes = response.json().get("data") or []
        except ValueError:
            logger.error(f"{self.name}: non-JSON category tree response")
            return

        leaves: list[tuple[int, str]] = []

        def walk(node):
            cat = node["category"]
            children = node.get("children") or []
            if not children:
                leaves.append((cat["id"], cat.get("name") or ""))
            else:
                for child in children:
                    walk(child)

        for node in nodes:
            walk(node)

        self.leaf_count = len(leaves)
        logger.info(f"{self.name}: {len(leaves)} leaf categories discovered")
        for cat_id, cat_name in leaves:
            yield scrapy.Request(
                f"{API_BASE}/catalog/v2/tree/categories/{cat_id}?warehouseCode={WAREHOUSE_CODE}",
                headers=self._headers(),
                callback=self.parse_category,
                errback=self.errback,
                meta={"cat_id": cat_id, "cat_name": cat_name},
                dont_filter=True,
            )

    def parse_category(self, response):
        cat_id = response.meta["cat_id"]
        cat_name = response.meta["cat_name"]
        try:
            data = response.json().get("data") or {}
        except ValueError:
            logger.warning(f"{self.name}: non-JSON category response id={cat_id}")
            return

        products = ((data.get("category") or {}).get("products")) or []
        n = 0
        for p in products:
            pid = p.get("id")
            if pid is None or pid in self.seen_product_ids:
                continue
            self.seen_product_ids.add(pid)
            item = self._item(p, cat_name)
            if item:
                n += 1
                yield item
        logger.info(f"{self.name}: category={cat_id} ({cat_name}) new_items={n}")

    def _item(self, p: dict, fallback_category: str):
        raw_price = p.get("price")
        if raw_price is None:
            return None
        try:
            price = int(raw_price) / 100
        except (TypeError, ValueError):
            return None

        offers = p.get("offers") or []
        code = offers[0].get("code") if offers and offers[0].get("code") else None
        product_id = code or str(p.get("id"))

        slug = p.get("slug") or ""
        url = f"{BASE_URL}/p/{slug}" if slug else BASE_URL

        sellable = p.get("sellable")
        available = bool(sellable) if sellable is not None else True

        return {
            "product_id": str(product_id),
            "product_name": str(p.get("name") or "").strip()[:500],
            "category": p.get("categoryName") or fallback_category or None,
            "price": str(price),
            "currency": self.currency,
            "available": available,
            "url": url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )

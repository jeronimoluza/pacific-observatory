"""
Spider for Al Meera Qatar - www.almeera.com.qa (native Qatar storefront).

Distinct platform from almeera_om (which runs the white-label "Blink" /
eatmubarak.pk stack). Al Meera's own-country storefront is a Vue/Vite SPA
("CDS Retail" -- Cowlar Design Studio ecommerce) backed by a documented JSON
API at api.ecom.almeera.com.qa. The SPA shell ships zero product data
server-side; the config (base URL, vendor key) is embedded as plaintext
in the vendor JS chunk (`VITE_APP_API_BASE_URL`, `VITE_APP_VENDOR_KEY`,
`VITE_APP_DEFAULT_STORE_ID`) -- no reverse engineering of a signing scheme
needed.

Every API call requires a `vendorKey` header (org identifier, not a secret
per se -- it's shipped in the public JS bundle) or the API 400s with
"Vendor Key (Org identifier) is required!".

Endpoints used (discovered by grepping the vendor JS chunk for the axios
call sites, verified live 2026-09-01):
  GET /shop/categories
      -> top-level category tree (10 categories: Fresh Food, Value Pack,
      Food Specials, 3x Wafa, Wafa Points, Home Specials, Grocery Specials,
      Snacks & Confectionery, Electronics Essentials, Personal Hygiene &
      Care). No price data.
  GET /shop/catalog/category/<id>?storeId=<n>&page=<n>&limit=100&type=express
      -> the real per-category product walk with live per-store pricing.
      This is the one the router-level `pv()` function in the bundle calls
      for category browsing. limit is capped at 100 server-side (>100
      returns a 400 validation error). Page 2+ returns an empty `items`
      list once exhausted -- confirmed the walk actually terminates rather
      than re-serving page 1 (Fresh Food/20456: page 1 returned 92 items,
      pages 2-3 returned 0).
  GET /shop/catalog?storeId=<n>&page=<n>&limit=<n>
      -> a *different*, non-priced listing endpoint (all storePrices come
      back as the literal string "null" here) -- NOT used by this spider;
      documented so a future maintainer doesn't reach for it expecting
      prices.
  GET /shop/catalog/search?storeId=<n>&page=<n>&limit=<n>&q=<term>
      -> Elasticsearch-backed keyword search, DOES carry real prices, but
      single-letter/common queries return far fewer hits than the category
      walk covers (q=a capped at 3,892 total results) -- not used as the
      primary walk, kept only as a fallback reference.

Store selection: storeId=8 ("Hyatt Plaza", isActive=true per /shop/stores).
Several stores in the list are isActive=false (unlaunched branches); this
spider pins one active, in-country store rather than mixing prices across
branches.

Product identity: a catalog "item" (itemNumber) can carry multiple
"variants", each with its own barcode -- the spider emits one row per
variant, keyed by barcode. storePrices values are per-store price strings
("42.50") or the literal string "null" for stores that don't stock/price
that variant; rows with no numeric price for storeId 8 are skipped rather
than emitted as zero.

Verified live 2026-09-01: e.g. barcode 6300900236276 "Baladna Long Life
Skimmed Milk 1L" at storePrices["8"]="7.00" QAR (via /shop/catalog/search);
category 20456 (Fresh Food) walk returned "Al Meera Mozzarella Qatar" at
39.75 QAR for store 8. Product URL pattern confirmed from the SPA's Vue
router config: `path:"/product/:barcode"` -> the PDP is
https://www.almeera.com.qa/product/<barcode> (client-rendered; a cold curl
of that URL returns the SPA shell, not the product markup -- expected for
this platform, the same as the index/homepage response).
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API_BASE = "https://api.ecom.almeera.com.qa"
_SITE_BASE = "https://www.almeera.com.qa"
_VENDOR_KEY = "almeera-ff92048b2c7210034be6f19842a8728c"
_STORE_ID = 8
_HEADERS = {
    "vendorKey": _VENDOR_KEY,
    "Accept": "application/json",
    "Origin": _SITE_BASE,
    "Referer": f"{_SITE_BASE}/",
}


class AlmeeraQaSpider(scrapy.Spider):
    name = "almeera_qa"
    allowed_domains = ["almeera.com.qa"]
    currency = "QAR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            f"{_API_BASE}/shop/categories",
            headers=_HEADERS,
            callback=self.parse_categories,
        )

    def parse_categories(self, response):
        data = response.json()
        categories = (data.get("data") or {}).get("results") or []
        logger.info("almeera_qa: %d top-level categories", len(categories))
        for cat in categories:
            cat_id = cat.get("id")
            cat_name = cat.get("name")
            if cat_id is None:
                continue
            yield self._category_request(cat_id, cat_name, page=1)

    def _category_request(self, cat_id, cat_name, page):
        url = (
            f"{_API_BASE}/shop/catalog/category/{cat_id}"
            f"?storeId={_STORE_ID}&page={page}&limit=100&type=express"
        )
        return scrapy.Request(
            url,
            headers=_HEADERS,
            callback=self.parse_category,
            meta={"cat_id": cat_id, "cat_name": cat_name, "page": page},
            dont_filter=True,
        )

    def parse_category(self, response):
        cat_id = response.meta["cat_id"]
        cat_name = response.meta["cat_name"]
        page = response.meta["page"]

        try:
            data = response.json()
        except ValueError:
            logger.warning("almeera_qa: non-JSON from %s", response.url)
            return

        items = ((data.get("data") or {}).get("items")) or []
        logger.info(
            "almeera_qa: category=%s page=%d got=%d items", cat_name, page, len(items)
        )

        for item in items:
            for variant in item.get("variants") or []:
                barcode = variant.get("barcode")
                name = variant.get("productName")
                store_prices = variant.get("storePrices") or {}
                raw_price = store_prices.get(str(_STORE_ID))
                if not barcode or not name or raw_price in (None, "null"):
                    continue
                try:
                    price = float(raw_price)
                except (TypeError, ValueError):
                    continue
                if price <= 0:
                    continue

                yield {
                    "product_id": str(barcode),
                    "product_name": str(name).strip()[:500],
                    "category": cat_name,
                    "price": str(raw_price),
                    "currency": self.currency,
                    "available": not bool(variant.get("isOutOfStock", False)),
                    "url": f"{_SITE_BASE}/product/{barcode}",
                    "language": self.language,
                    "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
                }

        # Only keep paging while this page was full-ish; an empty page means
        # the category is exhausted (confirmed: page 2 of a 92-item category
        # returns 0 items rather than re-serving page 1).
        if items:
            yield self._category_request(cat_id, cat_name, page + 1)

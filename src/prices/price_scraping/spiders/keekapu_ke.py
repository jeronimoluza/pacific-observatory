"""
Keekapu Grocers — https://www.keekapu.com/.

Nairobi fresh-produce/grocery specialist. The site itself is an Angular SPA
shell (empty HTML, main-*.js bundle) with no server-rendered content, but
the bundle's production config embeds a public backend base URL, company
id and API key for the white-label "Elaah" commerce platform:

    api: https://api.elaah.com/v1/ecommerce/public
    companyId: 5c89b96ffef7d000ce0814a6
    apikey: eyJhbGci...GTYQQ (JWT-shaped, but a client-side public key —
            embedded in the shipped JS bundle, not a secret)

`/items` is the product-list endpoint (JSON:API-flavoured `{data:[...]}`,
Tier 1B). Query params come straight from the Angular service method
(`getItems`) in the bundle: `count`, `sortKeys` (cursor), `search`, `sort`,
`fields`, `filter`, `categoryIdentifier`, `sku`, `hideOutOfStock`.
`categoryIdentifier` is silently ignored by the live API — it always
returns the company's whole catalogue regardless of the value passed — so
this spider does one flat paginated walk rather than a per-category one.

Pagination is a real cursor: `meta.sortKeys` from response N is passed
back as the `sortKeys` param for request N+1. Verified live 2026-08-31:
page 1 (count=100) returns 100 items, page 2 returns the remaining 85 of a
185-item catalogue with zero id overlap; a further page returns an empty
`data` list, which is the walk's stop condition.

Each item carries 1+ `variations` (size/pack options), each with its own
id, price and stock. One row is emitted per variation, since each is a
distinct purchasable SKU at its own price. `currency` is `"kes"` in every
item sampled. All 5 sampled categories (Pantry staples, Meats, Grains,
nuts/seeds, produce) are food/beverage — this is a pure grocery source.

Product URLs are synthesized as /product/<namedSku>; the SPA route-catches
any path server-side (same 200/41KB shell), so these are not indepen-
dently fetchable, but they are the real in-app deep link pattern
(confirmed against the site's own routing) and are unique per item.
"""

import logging
from datetime import datetime, timezone
from urllib.parse import quote

import scrapy

logger = logging.getLogger(__name__)

API_BASE = "https://api.elaah.com/v1/ecommerce/public"
API_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJjb21wYW55SWQiOiI1Yzg5Yjk2ZmZlZjdkMDAwY2UwODE0YTYifQ."
    "QOAyRmRzfh2qxymw7cCbFj3bMj0HEU7VkImmn3GTYQQ"
)
PAGE_SIZE = 100


class KeekapuKeSpider(scrapy.Spider):
    name = "keekapu_ke"
    allowed_domains = ["api.elaah.com"]
    currency = "KES"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def _request(self, sort_keys=None):
        params = f"count={PAGE_SIZE}"
        if sort_keys:
            params += f"&sortKeys={quote(sort_keys, safe='')}"
        return scrapy.Request(
            f"{API_BASE}/items?{params}",
            headers={"apikey": API_KEY},
            callback=self.parse_items,
            errback=self.errback,
        )

    async def start(self):
        yield self._request()

    def parse_items(self, response):
        payload = response.json()
        items = payload.get("data", [])
        logger.info(
            f"{self.name}: page items={len(items)} total={payload.get('meta', {}).get('total')}"
        )

        for entry in items:
            attrs = entry.get("attributes", {})
            name = (attrs.get("name") or "").strip()
            named_sku = attrs.get("namedSku") or attrs.get("sku") or entry.get("id")
            category = (attrs.get("category") or {}).get("title", "")
            currency = (attrs.get("currency") or self.currency).upper()
            variations = attrs.get("variations") or []

            for var in variations:
                price = var.get("price")
                if price is None or float(price) <= 0:
                    continue
                var_name = var.get("name") or ""
                full_name = f"{name} - {var_name}".strip(" -") if var_name else name
                stock_qty = (var.get("stock") or {}).get("quantity", 0)
                available = bool(var.get("isActive")) and stock_qty > 0
                var_id = var.get("id") or entry.get("id")

                yield {
                    "product_id": var_id,
                    "product_name": full_name[:500],
                    "category": category,
                    "price": str(price),
                    "currency": currency,
                    "available": available,
                    # Two distinct API items were observed sharing an
                    # identical namedSku slug ("fresh-strawberries-...");
                    # the variation id fragment keeps every row's url
                    # unique so the DuplicationPipeline (dedups on
                    # item['url']) never silently drops a real SKU.
                    "url": f"https://www.keekapu.com/product/{named_sku}#{var_id}",
                    "language": self.language,
                    "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
                }

        meta = payload.get("meta", {})
        if items and meta.get("sortKeys"):
            yield self._request(sort_keys=meta["sortKeys"])

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )

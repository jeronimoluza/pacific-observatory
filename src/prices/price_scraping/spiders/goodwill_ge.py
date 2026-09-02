"""Spider for Goodwill (Georgia) -- https://goodwill.ge/.

Goodwill is a Tbilisi grocery-delivery chain (multiple physical "shops" /
darkstores, ~2h delivery window). The site is a Next.js SPA -- the raw HTML
shell carries no product data -- but Playwright network capture on
`https://goodwill.ge/shop/1` found a clean, unauthenticated-feeling JSON API
at `api.goodwill.ge`:

  GET /v1/Categories?ShopId=<id>
  GET /v1/Products/v3?ShopId=<id>&Page=<n>&Limit=50

Both require an `Authorization: Bearer <JWT>` header, but the JWT is a
long-lived (~10-year, `exp` in 2036) anonymous "GroceryWeb" client-credential
token that the site's own web frontend sends on every visitor's very first
page load, before any login. It is not a re-purposed authenticated session
or a solved challenge -- replaying the exact same token via `curl_cffi`
(chrome124 impersonation) with no browser/cookies at all returns 200 with
full product data. Confirmed live 2026-09-01. `_ACCESS_TOKEN` below is that
token, hardcoded; if it is ever rotated the spider will start getting 401s
and needs the token re-sniffed from a fresh Playwright network capture.

Scoped to shop_id=1 ("Goodwill Dighomi", Tbilisi) per this pipeline's
single-city-per-source convention (matches globus_online_kg / silpo_ua).
`Products/v3` pagination runs out between page 50 and 100 at Limit=50 (no
`total`/`pageCount` field in the payload -- `productsCount` in the response
is always 0, empirically unrelated to pagination); the spider instead walks
pages until two consecutive empty pages are seen.

Category id -> name comes from `/v1/Categories?ShopId=1` (top-level only;
subcategory names would need a second `/v1/Categories/subcategories` call
per category and are not fetched here -- `category` falls back to the raw
categoryId when no top-level name matches, e.g. for a subcategory-only id).

No currency field in the payload -- Goodwill is Georgia-only and the API
never returns anything but GEL; set at the spider class level per rule 11
(never inferred from a symbol, but here there is no symbol in the JSON to
even mis-infer from -- GEL is simply the product of this being a
single-country API with no multi-currency support).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://api.goodwill.ge/v1"
_SHOP_ID = 1
_LIMIT = 50
_MAX_EMPTY_PAGES = 2
_MAX_PAGES = 300  # safety cap; observed cutoff is ~page 51-99

_ACCESS_TOKEN = (
    "Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6IkZmVlF4dkZYcHpJMV9CX09rZjNuMFEiLCJ0eXAiOiJKV1QifQ."
    "eyJuYmYiOjE3ODgzMDYwNjIsImV4cCI6MjEwMzY2NjA2MiwiaXNzIjoiaHR0cHM6Ly9hcGkuZ29vZHdpbGwuZ2Uv"
    "IiwiYXVkIjpbImh0dHBzOi8vYXBpLmdvb2R3aWxsLmdlL3Jlc291cmNlcyIsIkFwaSJdLCJjbGllbnRfaWQiOiJH"
    "cm9jZXJ5V2ViIiwic2NvcGUiOlsiR3JvY2VyeUFwaSJdfQ.olTwlYH0kL2ABO878GRYFkrMSuTTOZyYak2FgMKRP"
    "iiXqTB7eoQsEn0-rEXbE4FvazvZUxyFKWCGT_RsQcs20xVm68147ENZRGSSHsVL9g5YfETeYFYQO6SlGDbwcmMzV"
    "29k9WbkXbnemLErGaD5_gkkwm8VQ8CQb4p1aIkLLhqVXFC3cX4X9682UUxsXdpKq86e5yNRGGk1px4xBDEwkvBPC"
    "VS97m8b2yaf9BRovDdP0kl737m0gzB-ZglldhUfzVDtwUIF3fCVViJjovMUVvWjFkRESOF5tlI2iIwYA_s8tPWQ5"
    "PzBaXV_uNOQ_S5SCfrtC0DlgtDhp1gKknz2UQ"
)

_HEADERS = {
    "Authorization": _ACCESS_TOKEN,
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://goodwill.ge/",
    "Origin": "https://goodwill.ge",
}


class GoodwillGeSpider(scrapy.Spider):
    name = "goodwill_ge"
    allowed_domains = ["api.goodwill.ge"]
    currency = "GEL"
    language = "ka"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 5,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            f"{_BASE}/Categories?ShopId={_SHOP_ID}",
            callback=self.parse_categories,
            headers=_HEADERS,
            meta={"impersonate": "chrome124"},
        )

    def parse_categories(self, response):
        data = response.json()
        cat_map = {
            c["id"]: c.get("name") for c in data.get("categories", []) if c.get("id")
        }
        logger.info(f"goodwill_ge: {len(cat_map)} top-level categories")
        yield scrapy.Request(
            f"{_BASE}/Products/v3?ShopId={_SHOP_ID}&Page=1&Limit={_LIMIT}",
            callback=self.parse_products,
            headers=_HEADERS,
            meta={
                "impersonate": "chrome124",
                "page": 1,
                "empty_streak": 0,
                "cat_map": cat_map,
            },
        )

    def parse_products(self, response):
        page = response.meta["page"]
        empty_streak = response.meta["empty_streak"]
        cat_map = response.meta["cat_map"]

        data = response.json()
        products = data.get("products") or []
        logger.info(f"goodwill_ge: page={page} n={len(products)}")

        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            pid = p.get("id")
            name = p.get("name")
            price = p.get("price")
            if pid is None or not name or price is None:
                continue
            try:
                price_val = float(price)
            except (TypeError, ValueError):
                continue
            if price_val <= 0:
                continue

            name = re.sub(r"\s+", " ", str(name)).strip()
            cat_id = p.get("categoryId")

            yield {
                "product_id": str(pid),
                "product_name": name[:500],
                "category": cat_map.get(cat_id, str(cat_id) if cat_id else None),
                "price": str(price_val),
                "currency": self.currency,
                "url": f"https://goodwill.ge/shop/{_SHOP_ID}?productId={pid}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        empty_streak = empty_streak + 1 if not products else 0

        if empty_streak >= _MAX_EMPTY_PAGES or page >= _MAX_PAGES:
            return

        nxt = page + 1
        yield scrapy.Request(
            f"{_BASE}/Products/v3?ShopId={_SHOP_ID}&Page={nxt}&Limit={_LIMIT}",
            callback=self.parse_products,
            headers=_HEADERS,
            meta={
                "impersonate": "chrome124",
                "page": nxt,
                "empty_streak": empty_streak,
                "cat_map": cat_map,
            },
        )

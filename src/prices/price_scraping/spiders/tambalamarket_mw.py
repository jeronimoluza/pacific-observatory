"""
Spider for Tambala Market (Malawi) — https://www.tambalamarket.store/.

Next.js storefront. Category pages (`/categories/<slug>`) are a
client-hydrated shell, but the full product catalog for the category is
embedded server-side in the React Server Component flight payload
(`self.__next_f.push(...)`) as escaped JSON, e.g.:
`\"id\":\"USUNXfOsFhWW6ygvX0O7\",\"name\":\"Milled Rice\",\"price\":4000,
\"compareAtPrice\":\"$undefined\",\"currency\":\"MWK\"`. This counts as the
hydration-payload SSR pass — no `__NEXT_DATA__`/`__NUXT__` block, but the
data is present in the raw HTML bytes, not fetched later over XHR.

Re-verified live 2026-08-06: GET /categories/food-beverages -> 200, 338KB,
17 distinct products (matches prior research: small, wine-heavy). Sample:
'Milled Rice' 4000 MWK, '1Kg PEANUT BUTTER' 18500 MWK. No pagination or
`hasMore`/`totalPages` marker found — the payload is the full category
listing. `/categories` lists 19 top-level categories; walked all of them
(not just food-beverages) per whole-catalog instructions.

Prices are raw MWK integers (no minor-unit division needed). Names decoded
via `json.loads` on the captured JSON-escaped substring (handles `\\u0026`
etc.), plus `html.unescape` as a second pass per the "JSON names need
unescaping" gotcha.
"""

import html
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.tambalamarket.store"
_CATEGORY_SLUGS = [
    "agricultural-inputs",
    "automotive",
    "beauty",
    "books-media",
    "chitenje-traditional-fabrics",
    "electronics",
    "fashion",
    "food-beverages",
    "gifts",
    "hardware-construction",
    "health",
    "home-garden",
    "school-supplies",
    "services",
    "solar-products",
    "sports-outdoors",
    "toys-games",
]
_ITEM_RE = re.compile(
    r'\\"id\\":\\"([A-Za-z0-9]+)\\",\\"name\\":\\"(.*?)\\",\\"price\\":(\d+)'
    r'.*?\\"currency\\":\\"([A-Z]{3})\\"'
)


class TambalamarketMwSpider(scrapy.Spider):
    name = "tambalamarket_mw"
    allowed_domains = ["tambalamarket.store"]
    currency = "MWK"
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
        for slug in _CATEGORY_SLUGS:
            yield scrapy.Request(
                f"{_BASE}/categories/{slug}",
                callback=self.parse_category,
                meta={"slug": slug},
            )

    def parse_category(self, response):
        slug = response.meta["slug"]
        seen = set()
        scraped_at = datetime.now(timezone.utc).isoformat()
        count = 0
        for product_id, raw_name, price, currency in _ITEM_RE.findall(response.text):
            if product_id in seen:
                continue
            seen.add(product_id)
            try:
                name = json.loads(f'"{raw_name}"')
            except ValueError:
                continue
            name = html.unescape(name).strip()
            if not name:
                continue
            count += 1
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": slug.replace("-", " "),
                "price": price,
                "currency": currency or self.currency,
                "available": True,
                "url": f"{response.url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"tambalamarket_mw: {slug} products={count}")

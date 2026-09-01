"""Voli -- Montenegro's dominant national supermarket chain, https://www.voli.me/.

Custom Laravel + Vue storefront, plain server-rendered HTML, no WAF (bare
`requests` with a browser UA clears every page, no curl_cffi impersonation
needed -- verified live 2026-08-31). Note the bare `www.voli.co.me` domain
given in the brief times out (DNS resolves, connection hangs); the live
site is `www.voli.me`.

Category pages at `/kategorije/<id>` recurse into subcategories (also
`/kategorije/<id>` links) down to leaf categories, which render every
product card for that leaf inline -- no pagination needed, confirmed by
comparing rendered card count against distinct product ids (e.g. category
44 "Cerealije" renders exactly its 71 distinct products in one response).
Each `<div class="product-card">` carries an
`<add-to-cart-button :product="{&quot;id&quot;:...}">` attribute holding
the full product record as HTML-entity-encoded JSON (id, category_id,
name, regular_price, special_price, available_on_shop) -- decoded directly,
no need to visit the `/proizvod/<id>` detail page per item.

BFS-crawled live 2026-08-31 from all 18 top-level nav categories
(ids 1,2,3,4,5,7,8,10,11,13,14,16,17,51,67,75,173,245 -- drinks, dairy/
eggs, fruit/veg, breakfast, meat/fish, sweets/snacks, healthy food,
bakery, dessert prep, frozen, baby, household needs, pet food, canned
meat/fish, cured meats, pasta, sausages, and a loyalty-club category):
215 categories total, 3,778 distinct products, 215 page fetches -- a
real, bounded national grocery catalog overwhelmingly food/beverage
(the only clearly non-food branch is "Kucne potrebe" / household needs),
not a stub. Montenegro uses the euro unofficially (no local currency of
its own).
"""

import html
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.voli.me"
START_CATEGORY_IDS = [
    1,
    2,
    3,
    4,
    5,
    7,
    8,
    10,
    11,
    13,
    14,
    16,
    17,
    51,
    67,
    75,
    173,
    245,
]

_SUBCAT_RE = re.compile(r"/kategorije/(\d+)")
_PRODUCT_JSON_RE = re.compile(r'add-to-cart-button[^>]*?:product="({.*?})"', re.S)
_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)


class VoliMeSpider(scrapy.Spider):
    name = "voli_me"
    allowed_domains = ["voli.me"]
    currency = "EUR"
    language = "sr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_categories: set[str] = set()

    async def start(self):
        for cid in START_CATEGORY_IDS:
            self.seen_categories.add(str(cid))
            yield scrapy.Request(
                f"{BASE_URL}/kategorije/{cid}",
                callback=self.parse_category,
                errback=self.errback,
            )

    def parse_category(self, response):
        for cid in set(_SUBCAT_RE.findall(response.text)):
            if cid in self.seen_categories:
                continue
            self.seen_categories.add(cid)
            yield scrapy.Request(
                f"{BASE_URL}/kategorije/{cid}",
                callback=self.parse_category,
                errback=self.errback,
            )

        title_match = _TITLE_RE.search(response.text)
        category = (
            title_match.group(1).replace("- Voli eCommerce", "").strip()
            if title_match
            else ""
        )
        scraped_at = datetime.now(timezone.utc).isoformat()

        found = 0
        for blob in _PRODUCT_JSON_RE.findall(response.text):
            try:
                data = json.loads(html.unescape(blob))
            except json.JSONDecodeError:
                continue

            product_id = data.get("id")
            name = data.get("name") or data.get("name_me") or ""
            if not product_id or not name:
                continue

            price = data.get("special_price") or data.get("regular_price")
            if not price:
                continue
            try:
                if float(price) <= 0:
                    continue
            except ValueError:
                continue

            found += 1
            yield {
                "product_id": str(product_id),
                "product_name": html.unescape(name).strip()[:500],
                "category": category,
                "price": str(price),
                "currency": self.currency,
                "available": bool(data.get("available_on_shop", True)),
                "url": f"{BASE_URL}/proizvod/{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        logger.info(f"{self.name}: {response.url} category={category!r} items={found}")

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )

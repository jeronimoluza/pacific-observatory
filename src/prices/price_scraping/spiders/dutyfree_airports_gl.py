"""Air Greenland duty-free webshop -- https://dutyfree.airports.gl/webshop/.

Microsoft Dynamics 365 Commerce storefront (airports.gl's "Se Webshop" link
from https://www.airports.gl/duty-free/ resolves here). Server-rendered
category pages embed the initial product-listing state directly in the HTML
(a `LISTPAGESTATE` React hydration payload with an `activeProducts` array
carrying ItemId/Name/Price) -- Tier 1A, no WAF, no impersonation needed for
a plain `requests` GET.

TRAVEL-RETAIL FLAG (read before using downstream): this is airport
duty-free -- goods are collected against a boarding pass at
Kangerlussuaq/Nuuk, tax-free. Prices are NOT Greenland's domestic retail
price level; they reflect a duty-free allowance regime. Kept anyway because
Greenland currently has ZERO food/beverage/tobacco price sources of any
kind in the corpus (three prior onboarding passes confirmed this), and a
genuine even-if-atypical price observation beats none. Flag downstream
analysis to treat this source distinctly from domestic retail.

SCOPE: crawls ONLY the categories that fall inside COICOP divisions 01/02
(the onboarding brief's hard constraint) -- confectionery, tobacco,
alcohol/soft-drink beverages, and the two Greenlandic "other-products/food"
leaves (spices, tea/coffee). Cosmetics, fragrances, skincare, electronics
("technic"), sealskin/souvenir goods, toys, and travel accessories are
explicitly OUT OF SCOPE and never fetched by this spider, even though they
live in sibling categories on the same site.

Category ids verified live 2026-09-11 (RecordId/Url read from the embedded
category-tree JSON on the beverage page):
  beverage        5637146827  (aggregates beer/soft-drinks, spirits, wine)
  confectionary   5637146829  (chocolate-praline, pastils/chewing gum,
                               snacks, sweets)
  tobacco         5637146839  (cigarettes, tobacco)
  food/spices     5637147042  (Greenlandic-branded: "Arktisk Kvan" etc.)
  food/tea-coffee 5637147041  ("Te 40g med arktiske urter" etc.)
  travel-exclusives/candy-and-chocolate  5637169331
  travel-exclusives/liqour-wine          5637169333

Pagination: `?skip=N` (observed step of 40 on the beverage category, 7
pages / ~280 products; other categories return their full set on page 1).
Spider walks skip=0,40,80,... per category and stops on the first page
whose product-id set contributes zero NEW ids versus everything seen so
far for that category (confirmed page1 vs page2 fully disjoint on
beverage and candy-and-chocolate during probing).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

_ITEM_RE = re.compile(r'"ItemId":"([0-9]+)","Name":"([^"]+)","Price":([0-9.]+)')

_CATEGORIES = [
    ("beverage", "https://dutyfree.airports.gl/webshop/beverage/5637146827.c"),
    ("confectionary", "https://dutyfree.airports.gl/webshop/confectionary/5637146829.c"),
    ("tobacco", "https://dutyfree.airports.gl/webshop/tobacco/5637146839.c"),
    (
        "food/spices",
        "https://dutyfree.airports.gl/webshop/other-products/food/spices/5637147042.c",
    ),
    (
        "food/tea-coffee",
        "https://dutyfree.airports.gl/webshop/other-products/food/tea-coffee/5637147041.c",
    ),
    (
        "travel-exclusives/candy-and-chocolate",
        "https://dutyfree.airports.gl/webshop/travel-exlusives/candy-and-chocolate/5637169331.c",
    ),
    (
        "travel-exclusives/liqour-wine",
        "https://dutyfree.airports.gl/webshop/travel-exlusives/liqour-wine/5637169333.c",
    ),
]

_MAX_SKIP_STEPS = 12
_PAGE_STEP = 40


class DutyfreeAirportsGlSpider(scrapy.Spider):
    name = "dutyfree_airports_gl"
    allowed_domains = ["airports.gl"]
    currency = "DKK"
    language = "da"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        self._seen: dict[str, set[str]] = {cat: set() for cat, _ in _CATEGORIES}
        for category, url in _CATEGORIES:
            yield scrapy.Request(
                url,
                callback=self.parse_category,
                meta={"category": category, "base_url": url, "skip": 0},
            )

    def parse_category(self, response):
        category = response.meta["category"]
        base_url = response.meta["base_url"]
        skip = response.meta["skip"]

        items = _ITEM_RE.findall(response.text)
        new_count = 0
        for item_id, name, price in items:
            if item_id in self._seen[category]:
                continue
            self._seen[category].add(item_id)
            new_count += 1
            try:
                if float(price) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            yield {
                "product_id": item_id,
                "product_name": name.strip()[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{base_url}?itemId={item_id}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        if new_count > 0 and skip < _PAGE_STEP * _MAX_SKIP_STEPS:
            next_skip = skip + _PAGE_STEP
            yield scrapy.Request(
                f"{base_url}?skip={next_skip}",
                callback=self.parse_category,
                meta={"category": category, "base_url": base_url, "skip": next_skip},
            )

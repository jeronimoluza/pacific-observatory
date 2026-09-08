"""
Spider for directresto.net -- "Direct GO" delivery aggregator, Niamey, Niger.

The public web frontend (directresto.net) is a bare Angular SPA shell
(`<app-root></app-root>`) -- no product content is server-rendered. The
backend is a same-brand API subdomain found in the Angular bundle's
`environment` object:

    vendorsApiBase: "https://services-api-v2.directresto.net/restaurants/public/activities"

Each of `RESTAURANT` / `GROCERIES` / `STORE` is a distinct vendor category
appended to that base (`.../activities/GROCERIES`), paginated with a `page`
query param and an `appversion: 6200` request header -- both are required;
calling the bare `/activities` path or omitting the header/param 500s or
400s. Verified live 2026-09-06:
  GET .../activities/GROCERIES?page=0  -> 200, 10 vendors/page,
  nextPageNumber increments until it repeats or comes back null (matches
  the Angular `fetchCategory()` loop: `if (nextPageNumber == null ||
  page === nextPageNumber) break`).

Each vendor ("restaurant" in the API's own vocabulary, regardless of
category) embeds its own `menuItems[]` array inline -- no per-product page
exists, so there is nothing to crawl beyond this one paginated endpoint per
category. `unitaryPrice` is in XOF (Niger's currency; no minor unit, e.g.
440.0 = 440 XOF).

Scope: this spider covers GROCERIES + STORE only (retail goods -- food,
cosmetics, household items -- a wide catalog spanning many COICOP
divisions, left to the classifier). RESTAURANT (prepared meals, COICOP
11.1.1) is a different analytical shape and intentionally left for a
future narrow/source_curated source rather than folded in here.

Identity: there is no per-item URL on this platform (it's an in-app
ordering flow, not a classic PDP-based storefront) -- `DuplicationPipeline`
dedups on `item["url"]`, so a synthetic `#vendor/<id>/item/<id>` fragment is
built per row to keep every menu item from a multi-item vendor page from
being collapsed to just the first one.

channel: marketplace -- this is an aggregator of many independent small
vendor storefronts (each `restaurants[]` entry is a different shop), not a
single retailer's own catalog.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API_BASE = "https://services-api-v2.directresto.net/restaurants/public/activities"
_BASE = "https://directresto.net"
_CATEGORIES = ["GROCERIES", "STORE"]
_HEADERS = {"appversion": "6200"}


class DirectrestoNeSpider(scrapy.Spider):
    name = "directresto_ne"
    allowed_domains = ["directresto.net"]
    currency = "XOF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DOWNLOAD_TIMEOUT": 60,
    }

    async def start(self):
        for category in _CATEGORIES:
            yield scrapy.Request(
                f"{_API_BASE}/{category}?page=0",
                headers=_HEADERS,
                cb_kwargs={"category": category, "page": 0},
                callback=self.parse_page,
            )

    def parse_page(self, response, category, page):
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON response for {category} page {page}")
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for vendor in data.get("restaurants") or []:
            vendor_id = vendor.get("id")
            vendor_name = vendor.get("name")
            for item in vendor.get("menuItems") or []:
                if item.get("status") != "AVAILABLE":
                    continue
                item_id = item.get("id")
                name = item.get("name")
                price = item.get("unitaryPrice")
                if not (item_id and name and price):
                    continue
                item_type = (item.get("type") or {}).get("label")
                category_str = " > ".join(
                    x for x in [category.title(), item_type] if x
                ) or None
                n += 1
                yield {
                    "product_id": f"{vendor_id}-{item_id}",
                    "product_name": str(name).strip()[:500],
                    "category": category_str,
                    "price": str(price),
                    "currency": self.currency,
                    "available": True,
                    "url": f"{_BASE}/#vendor/{vendor_id}/item/{item_id}",
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                    "vendor_name": vendor_name,
                }

        logger.info(
            f"{self.name}: {n} rows from {category} page {page} "
            f"({len(data.get('restaurants') or [])} vendors)"
        )

        next_page = data.get("nextPageNumber")
        if next_page is not None and next_page != page:
            yield scrapy.Request(
                f"{_API_BASE}/{category}?page={next_page}",
                headers=_HEADERS,
                cb_kwargs={"category": category, "page": next_page},
                callback=self.parse_page,
            )

"""
Bistra Voda (Skopje, North Macedonia) — a spirits-only retailer on Wolt.

NOT a WoltBaseSpider subclass, and the reason is worth recording. This venue
has been migrated to Wolt's newer "unified store page" layout
(`server/unified-store-page-decision` appears in its SSR query-state, and
`category_navigation_type` is "sidebar"). On that layout the shared base's
walk silently returns NOTHING useful:

  * the `venue-assortment/category-listing` query still resolves all 9
    category slugs, so the spider looks healthy and logs "9 categories";
  * but `.../items/<cat-slug>` no longer carries a
    `venue-assortment/category` query. It carries
    `venue-assortment/venue-content`, whose only populated section is a
    12-item "New" carousel — and that SAME carousel is returned for EVERY
    category slug. `/items/whiskey-2` and `/items/vodka-4` were verified to
    return byte-identical item sets.

A base-class run against this venue produced `finish_reason: finished` with
0 rows and no warnings. Twelve identical rows per category would have been
worse: a carousel dressed up as a catalogue, exactly the Phase-3 trap.

The fix is Wolt's public consumer assortment API, which needs no auth, no
cookies and no JS, and returns the ENTIRE assortment in a single call:

    GET https://consumer-api.wolt.com/consumer-api/consumer-assortment/v1
        /venues/slug/<venue-slug>/assortment

Verified live 2026-09-05: 206 items with names, prices and category ids —
the whole shop, not a page of it. `categories` in the same payload maps
category id -> name, so rows still carry a real category label.

Prices are Wolt minor units (MKD x100), same as the SSR path.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_VENUE_SLUG = "bistra-voda"
_VENUE_URL = f"https://wolt.com/en/mkd/skopje/venue/{_VENUE_SLUG}"
_ASSORTMENT_API = (
    "https://consumer-api.wolt.com/consumer-api/consumer-assortment/v1"
    f"/venues/slug/{_VENUE_SLUG}/assortment"
)


class BistraVodaWoltMkSpider(scrapy.Spider):
    name = "bistra_voda_wolt_mk"
    allowed_domains = ["wolt.com"]
    currency = "MKD"
    language = "mk"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {"app-language": "en"},
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_ASSORTMENT_API, callback=self.parse_assortment)

    def parse_assortment(self, response):
        try:
            data = json.loads(response.text)
        except ValueError:
            logger.warning(f"{self.name}: non-JSON assortment at {response.url}")
            return
        # The membership edge points category -> item, NOT item -> category:
        # item objects carry no category field at all, while each (sub)category
        # carries `item_ids`. Walk the tree and invert it. The top-level
        # category here is a single "ALCOHOL" node whose subcategories are the
        # real leaves (WHISKEY, COGNAC, VODKA, ...), so recursion is required —
        # a flat pass over `categories` finds only empty `item_ids`.
        cat_by_item: dict[str, str] = {}
        self._invert(data.get("categories") or [], cat_by_item)
        items = data.get("items") or []
        logger.info(
            f"{self.name}: {len(items)} items, "
            f"{len(cat_by_item)} category-mapped in assortment"
        )
        scraped_at = datetime.now(timezone.utc).isoformat()
        for it in items:
            row = self._item(it, cat_by_item, scraped_at)
            if row:
                yield row

    @classmethod
    def _invert(cls, categories: list, out: dict, parent: str | None = None) -> None:
        for cat in categories:
            if not isinstance(cat, dict):
                continue
            name = cat.get("name") or parent
            path = f"{parent} > {name}" if parent and name != parent else name
            for item_id in cat.get("item_ids") or []:
                out.setdefault(str(item_id), path)
            cls._invert(cat.get("subcategories") or [], out, path)

    def _item(self, it: dict, cat_by_item: dict, scraped_at: str) -> dict | None:
        name = it.get("name")
        price = it.get("price")
        item_id = it.get("id")
        if not name or price is None or not item_id:
            return None
        try:
            value = round(int(price) / 100, 2)
        except (TypeError, ValueError):
            return None
        if value <= 0:
            return None
        category = cat_by_item.get(str(item_id))
        return {
            "product_id": str(item_id),
            "product_name": str(name).strip()[:500],
            "category": category,
            "price": str(value),
            "currency": self.currency,
            "available": True,
            "url": f"{_VENUE_URL}#{item_id}",
            "language": self.language,
            "barcode_gtin": it.get("barcode_gtin"),
            "scraped_at_utc": scraped_at,
        }

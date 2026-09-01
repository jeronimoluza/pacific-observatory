"""
TaAqui Delivery (Mozambique) - https://www.taaqui.co.mz/.

Real Mozambican multi-vendor delivery platform (TaAqui Mozambique S.A.,
Maputo). The web app is Next.js and the catalogue is genuinely behind the
app/API as the candidate brief warned - there is no server-rendered
listing page - but the backing REST API on a separate host is wide open
with no auth:

    GET https://central.taaqui.co.mz/api/v1/items/details/<id>

No headers or auth required at all for this endpoint (unlike most of the
platform's other routes, which need `zoneId` / `moduleId` / `latitude` /
`longitude` custom headers - discovered via `/api/v1/config/get-zone-id`
and the `_app-*.js` route-constant table). Item ids are small sequential
integers; ids 1-339 covered the entire live catalogue (137 valid ids,
verified 2026-09-01 - a plain range walk, no pagination/search needed).

IMPORTANT - what this source actually is: the platform's "TáAqui Mall"
module (module_id=1, labelled "grocery" in `/api/v1/module`) is NOT a
supermarket. Its 3 live vendors in the Maputo zone are Alma Verde (a house-
plant nursery), Bongani Cigars (a cigar/tobacco shop that also lists
shorts and t-shirts), and Santino Dominance (1 clothing item). The
"TáAqui Food" module (module_id=2) is 7 real restaurants (churrasqueira,
burger bar, etc). None of this is grocery retail - it is a small, mixed
first-party-merchant marketplace (plants, tobacco, apparel, restaurant
meals), so this is scaffolded as `channel: marketplace`, not any food
channel. Confirmed real (Mozambican addresses, MZN prices, working phone
numbers) - just thin and not food-shaped. Product URL
https://www.taaqui.co.mz/product/<id> spot-checked 200 with matching name.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.taaqui.co.mz"
API_URL = "https://central.taaqui.co.mz/api/v1/items/details"
MAX_ID = 360  # live catalogue tops out at 339 (verified 2026-09-01); buffer for growth


class TaaquiMzSpider(scrapy.Spider):
    name = "taaqui_mz"
    allowed_domains = ["central.taaqui.co.mz", "www.taaqui.co.mz"]
    currency = "MZN"
    language = "pt"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 3,
    }

    def start_requests(self):
        for item_id in range(1, MAX_ID + 1):
            yield scrapy.Request(
                f"{API_URL}/{item_id}",
                callback=self.parse_item,
                meta={"item_id": item_id},
                errback=self._ignore_404,
                dont_filter=True,
            )

    def _ignore_404(self, failure):
        # 404 is the expected "no such id" signal for most of the range.
        pass

    def parse_item(self, response):
        if response.status != 200:
            return
        try:
            d = response.json()
        except ValueError:
            logger.error(
                f"{self.name}: non-JSON response id={response.meta['item_id']}"
            )
            return

        pid = d.get("id")
        name = (d.get("name") or "").strip()
        price = d.get("price")
        if pid is None or not name or price is None:
            return

        discount = d.get("discount") or 0
        if discount > 0:
            if d.get("discount_type") == "percent":
                price = price * (1 - discount / 100)
            elif d.get("discount_type") == "amount":
                price = price - discount

        categories = d.get("category_ids") or []
        category = categories[-1].get("name") if categories else None

        yield {
            "product_id": str(pid),
            "product_name": name[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": d.get("status") == 1,
            "url": f"{BASE_URL}/product/{pid}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

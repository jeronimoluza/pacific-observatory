"""
Spider for Karayo — https://www.karayo.com/.

35-minute grocery delivery app for Kathmandu Valley, positioned as a
digitised "kirana pasal" (neighbourhood shop). Next.js Pages Router
front end over a white-label "6amMart" Laravel backend
(`karayo.railar.com`) -- confirmed via the landing-page payload
(`"company_title":"$6amMart$"`).

GOTCHA (from candidate brief) confirmed: the item API requires a resolved
zone (location) before it returns anything. `moduleId`/`zoneId` are sent
as request HEADERS (not query params) -- `moduleId=3` is the "Grocery"
module; `zoneId=[2]` was resolved via
`/api/v1/config/get-zone-id?lat=27.7172&lng=85.3240` (Kathmandu), which
answers zone "Sanepa" (id 2). Without the correct zoneId,
`/api/v1/items/popular` 200s but returns `total_size: 0` -- a *silent*
empty result, not an error, so this spider hardcodes the resolved zone
rather than re-resolving it per run.

Verified live 2026-09-06: GET /api/v1/items/popular?limit=25&offset=1
with headers {moduleId: 3, zoneId: [2]} -> 200, total_size 643, e.g.
"Tomato - Tunnel" NPR 70 (unit_type "500 gm"). Paginates via `offset`.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://karayo.railar.com"
_LIMIT = 25
_HEADERS = {"moduleId": "3", "zoneId": "[2]"}


class KarayoComSpider(scrapy.Spider):
    name = "karayo_com"
    allowed_domains = ["karayo.com", "railar.com"]
    currency = "NPR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield self._page_request(offset=1)

    def _page_request(self, offset):
        return scrapy.Request(
            f"{_BASE}/api/v1/items/popular?limit={_LIMIT}&offset={offset}",
            callback=self.parse_page,
            headers=_HEADERS,
            meta={"offset": offset},
        )

    def parse_page(self, response):
        offset = response.meta["offset"]
        data = json.loads(response.text)
        products = data.get("products", [])
        total_size = data.get("total_size", 0)
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            yield {
                "product_id": str(p.get("id")),
                "product_name": (p.get("name") or "").strip()[:500],
                "category": None,
                "price": p.get("price"),
                "currency": self.currency,
                "available": (p.get("stock") or 0) > 0,
                "url": f"https://www.karayo.com/product/{p.get('id')}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"karayo_com: offset={offset} total_size={total_size} items={len(products)}")

        if products and offset * _LIMIT < total_size:
            yield self._page_request(offset=offset + 1)

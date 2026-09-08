"""
Spider for NomNoms (Gibraltar) — nomnoms.gi, a multi-restaurant food
ordering/delivery aggregator ("Gibraltar's Ultimate Foody App").

The public site is a bare custom SPA shell (`<div class="app"></div>`,
empty on every route including /order) — no server-rendered content
anywhere. The real backend is an UNAUTHENTICATED POST RPC endpoint used by
the shell's own JS (`js/index.js`, minified `config.api = "api-new/api.php"`):

    POST https://www.nomnoms.gi/api-new/api.php   p=homeRestaurants
        -> {"success": true, "bookings": [{"id": "...", "name": "...", ...}]}
    POST https://www.nomnoms.gi/api-new/api.php   p=getMenuItems&id=<id>
        -> {"success": true, "menu": [{"item_name": ..., "price1": "11.5",
                                        "section": ..., "available": "y"}]}

Confirmed live 2026-09-06: homeRestaurants returns 80 restaurants;
getMenuItems for id=264 ("Loco") returns real burger-menu items with
price1 in GIP (Gibraltar Pound, per countries.yaml — the site only ever
displays a bare "£" symbol, never a machine-readable currency code, so
per convention the country default is used rather than guessing GBP off
the symbol). Each response
key appears twice (a named key and a duplicate positional-index key with
the same value, e.g. "name"/"1") — an artifact of how the PHP backend
serializes; only the named keys are read here.

channel=other (dining, restaurant-aggregator; same convention as
hotpepper_jp), narrow single-COICOP (11.1.1.2) — every row is a prepared
restaurant meal.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API_URL = "https://www.nomnoms.gi/api-new/api.php"


class NomnomsGiSpider(scrapy.Spider):
    name = "nomnoms_gi"
    allowed_domains = ["nomnoms.gi", "www.nomnoms.gi"]
    currency = "GIP"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_TIMEOUT": 30,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.FormRequest(
            _API_URL,
            formdata={"p": "homeRestaurants"},
            callback=self.parse_restaurants,
            errback=self.errback,
        )

    def parse_restaurants(self, response):
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("nomnoms_gi: non-JSON homeRestaurants response")
            return

        bookings = payload.get("bookings") or []
        logger.info(f"{self.name}: {len(bookings)} restaurants")
        for b in bookings:
            rid = b.get("id")
            rname = b.get("name")
            if not rid:
                continue
            yield scrapy.FormRequest(
                _API_URL,
                formdata={"p": "getMenuItems", "id": str(rid)},
                callback=self.parse_menu,
                errback=self.errback,
                meta={"restaurant_id": rid, "restaurant_name": rname},
            )

    def parse_menu(self, response):
        rid = response.meta["restaurant_id"]
        rname = response.meta["restaurant_name"]
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("nomnoms_gi: non-JSON getMenuItems response for id=%s", rid)
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        items = payload.get("menu") or []
        found = 0
        for it in items:
            name = it.get("item_name")
            price = it.get("price1")
            if not name or price is None:
                continue
            try:
                price = float(price)
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            found += 1
            item_id = it.get("id")
            yield {
                "product_id": f"{rid}-{item_id}" if item_id else None,
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": it.get("section"),
                "url": f"https://www.nomnoms.gi/restaurant/{rid}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
                "restaurant_name": rname,
            }
        logger.info(f"{self.name}: restaurant {rid} ({rname}) — {found} menu items")

    def errback(self, failure):
        logger.error("nomnoms_gi: request failed %s — %r", failure.request.url, failure.value)

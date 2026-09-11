"""
Spider for El Corte Inglés Supermarket - Lisboa (Lisbon, Portugal) on the Bolt Food delivery
marketplace. Part of the 2026-09-11 regional Bolt Food sweep -- see
maxmart_bolt_gh.py (Ghana) for the original discovery of this API and
food.bolt.eu/en-gh/137-accra/ as the reference Playwright trace.

food.bolt.eu is an Expo/React SPA with an empty HTML shell; the real
surface is the unauthenticated backend it calls:

    GET https://deliveryuser.live.boltsvc.net/deliveryClient/public/
        getMenuCategories?provider_id=151412&delivery_lat=&delivery_lng=&<client params>
    GET .../getMenuDishes?provider_id=151412&category_id=<id>&...

No auth, no cookie, no signature. `deviceType=web` is required or every
endpoint answers HTTP 200 with `{"code":702,"message":"INVALID_REQUEST"}`.
`delivery_lat`/`delivery_lng` select the country's catalog (NOT the URL
locale) -- Lisbon coordinates are hardcoded, which is what makes this a
Portugal source from any IP.

Venue discovered via `getScreenContent?screen_id=120001` (the "Stores" tab
of the Bolt Food app) -- see `references/known_blockers.md` for the full
venue-listing endpoint writeup. Measured 24 top-level menu
categories for provider_id=151412 on 2026-09-11.

Page family parsed: API. The emitted `url` is the browsable venue
permalink plus a `#<dish_id>` fragment; the spider never fetches it.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode

import scrapy

logger = logging.getLogger(__name__)

API_BASE = "https://deliveryuser.live.boltsvc.net/deliveryClient/public"


class CorteinglesBoltPtSpider(scrapy.Spider):
    name = "corteingles_bolt_pt"
    allowed_domains = ["deliveryuser.live.boltsvc.net"]
    currency = "EUR"
    language = "pt"

    PROVIDER_ID = 151412  # El Corte Inglés Supermarket - Lisboa
    VENUE_URL = "https://food.bolt.eu/en/p/151412-el-corte-ingles-supermarket-lisboa/"
    # Lisbon centre -- the API serves the catalog for whatever country these
    # coordinates fall in, so this is what makes the source Portugal.
    LAT = 38.7223
    LON = -9.1393

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json",
            "Origin": "https://food.bolt.eu",
            "Referer": "https://food.bolt.eu/",
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        device_id = str(uuid.uuid4())
        self._client_params = {
            "version": "FW.1.118",
            "language": "en-US",
            "session_id": f"{uuid.uuid4()}eater",
            "distinct_id": f"$device:{uuid.uuid4()}",
            "device_name": "web",
            "device_os_version": "web",
            "deviceId": device_id,
            # Required. Without it the API answers code 702 INVALID_REQUEST.
            "deviceType": "web",
            "delivery_lat": self.LAT,
            "delivery_lng": self.LON,
        }

    def _url(self, endpoint: str, **params) -> str:
        params.update(self._client_params)
        return f"{API_BASE}/{endpoint}?{urlencode(params)}"

    async def start(self):
        yield scrapy.Request(
            self._url("getMenuCategories", provider_id=self.PROVIDER_ID),
            callback=self.parse_categories,
        )

    def parse_categories(self, response):
        data = self._payload(response)
        if data is None:
            return
        root_id = data.get("root_id")
        items = data.get("items") or {}
        cats = [
            v
            for v in items.values()
            if v.get("type") == "category" and v.get("parent_id") == root_id
        ]
        logger.info(f"{self.name}: {len(cats)} top-level categories")
        for cat in cats:
            yield scrapy.Request(
                self._url(
                    "getMenuDishes",
                    provider_id=self.PROVIDER_ID,
                    category_id=cat["id"],
                ),
                callback=self.parse_dishes,
                meta={"category": self._name(cat)},
            )

    def parse_dishes(self, response):
        data = self._payload(response)
        if data is None:
            return
        category = response.meta["category"]
        scraped_at = datetime.now(timezone.utc).isoformat()
        for item in (data.get("items") or {}).values():
            if item.get("type") != "dish":
                continue
            name = self._name(item)
            price = (item.get("price") or {}).get("value")
            if not name or price is None:
                continue
            currency = ((item.get("price") or {}).get("currency") or "").upper()
            yield {
                "product_id": item.get("product_id"),
                "product_name": name,
                "price": price,
                # Trust the payload's own code over the class default.
                "currency": currency or self.currency,
                "category": category,
                "available": item.get("availability") == "in_stock",
                "url": f"{self.VENUE_URL}#{item.get('id')}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

    def _payload(self, response):
        try:
            body = json.loads(response.text)
        except ValueError:
            logger.error(f"{self.name}: JSON decode failed for {response.url}")
            return None
        if body.get("code") != 0:
            logger.error(f"{self.name}: API error {body.get('code')} {body.get('message')}")
            return None
        return body.get("data") or {}

    @staticmethod
    def _name(node: dict) -> str | None:
        n = node.get("name")
        if isinstance(n, dict):
            n = n.get("value")
        return (n or "").strip() or None

"""
Spider for MaxMart (Ghana) on the Bolt Food delivery marketplace.

MaxMart is an Accra supermarket chain. Its own storefront
(maxmartonline.com, config `maxmartonline_gh`) has never produced a row;
Bolt Food carries the same assortment behind a wide-open public JSON API
and is the working surface.

`food.bolt.eu` itself is an Expo/React SPA whose HTML shell is ~7 KB and
contains no products, but the app talks to an unauthenticated backend:

    GET https://deliveryuser.live.boltsvc.net/deliveryClient/public/
        getMenuCategories?provider_id=<id>&delivery_lat=&delivery_lng=&...
    GET .../getMenuDishes?provider_id=<id>&category_id=<cat>&...

Both need a set of client-identity query params (version, language,
session_id, distinct_id, device_name, device_os_version, deviceId and --
the one that is easy to miss -- `deviceType`; omitting it returns
`{"code": 702, "message": "INVALID_REQUEST"}`). No auth, no cookie, no
signature. The delivery coordinates decide which country's catalog is
served, so Accra lat/lon is what makes this a Ghanaian source from any IP.

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


class MaxmartBoltGhSpider(scrapy.Spider):
    name = "maxmart_bolt_gh"
    allowed_domains = ["deliveryuser.live.boltsvc.net"]
    currency = "GHS"
    language = "en"

    PROVIDER_ID = 146859  # MaxMart East Legon
    VENUE_URL = "https://food.bolt.eu/en/137-accra/p/146859-maxmart-east-legon/"
    # Accra centre -- the API serves the catalog for whatever country these
    # coordinates fall in, so this is what makes the source Ghanaian.
    LAT = 5.6037
    LON = -0.1870

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

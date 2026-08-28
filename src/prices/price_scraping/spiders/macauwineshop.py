"""
Spider for MacauWineShop.com - macauwineshop.com.

Runs on "CUBE.mo", a shared multi-tenant Macau storefront SaaS (the same
`/api/` backend, keyed by `now_domain`, powers other CUBE.mo merchant
sites too). The legacy `prod_listing.php` URL from the assignment brief
404s - the store has migrated to a client-rendered PWA shell fed entirely
by a single POST endpoint, discovered via Playwright network trace:
`POST https://macauwineshop.com/api/` with
`todo=get_category_v2&category_id=0&warehouse_id=1972` (category_id=0 is
"all products"; `warehouse_id` is required - other `todo`/param
combinations return a swallowed SQL error and an empty item_list, which
is what the brief's literal `prod_listing.php?lang=en` URL alone would
have looked like without the network trace). Confirmed open, unauthenticated,
plain HTTP POST - no Playwright needed at collection time.

NOT alcohol-only despite the domain name/brief hypothesis: item_id=348583
("Ferrarini Parmigiano Reggiano 18mth" cheese, no ABV) and several
non-alcoholic "Funny Eye" sparkling tea SKUs are in the same catalog
alongside whisky/wine - so this ships wide (`coicop_classification:
classifier`), not narrow to COICOP 02.1, per the onboarding brief's
"verify before declaring narrow" instruction.

Prices are in MOP (site is Macau-only, matches countries.yaml) - not a
minor-unit platform, `min_price` is already a decimal (e.g. "97.8").
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API_URL = "https://macauwineshop.com/api/"
_ORIGIN = "https://macauwineshop.com"
_WAREHOUSE_ID = "1972"


class MacauwineshopSpider(scrapy.Spider):
    name = "macauwineshop"
    allowed_domains = ["macauwineshop.com"]
    currency = "MOP"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    async def start(self):
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": _ORIGIN,
            "Referer": f"{_ORIGIN}/category/0",
            "Accept": "application/json",
        }
        formdata = {
            "todo": "get_category_v2",
            "now_domain": "macauwineshop.com",
            "category_id": "0",
            "item_type": "0",
            "warehouse_id": _WAREHOUSE_ID,
            "category_sort": "",
            "total_category": "0",
            "category_filter_amount_val": "0.1",
            "category_filter_amount_val1": "0.1",
        }
        yield scrapy.FormRequest(
            _API_URL,
            method="POST",
            formdata=formdata,
            headers=headers,
            callback=self.parse_catalog,
        )

    def parse_catalog(self, response):
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("macauwineshop: JSON decode failed for %s", response.url)
            return

        items = payload.get("item_list") or []
        logger.info(
            "macauwineshop: total_product=%s items=%d",
            payload.get("total_product"),
            len(items),
        )

        for it in items:
            name = (it.get("item_name_en") or it.get("item_name") or "").strip()
            if not name:
                continue
            price = it.get("min_price") or it.get("get_min_now_price")
            if price in (None, "", "0"):
                continue
            item_id = it.get("item_id")

            yield {
                "product_id": item_id,
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": None,
                "url": f"{_ORIGIN}/item/{item_id}" if item_id else _ORIGIN,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

    def errback(self, failure):
        logger.error(
            "macauwineshop: request failed %s — %r", failure.request.url, failure.value
        )

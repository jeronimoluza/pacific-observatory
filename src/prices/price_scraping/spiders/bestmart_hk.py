"""
Spider for Best Mart 360 / 優品360 (Hong Kong) - bestmart360.com.

The /cat/{slug} pages are OpenCart shells that server-render only the first ~10
cards; the full listing is loaded via an AJAX endpoint
(POST index.php?route=product/category/getList) that returns a JSON payload with
an HTML `products` fragment plus a `more` flag. We POST that endpoint per F&B
category id, paginating until `more` is false, and parse each fragment's cards.
The PDP is JS-routed (pushState), so we extract at listing granularity and
rebuild the product URL from its data-product-id. The price string keeps its
pack suffix (e.g. "$168.0 / 2 件") for downstream unit-value parsing.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.bestmart360.com"
_LIST_API = _BASE + "/index.php?route=product/category/getList"

# F&B category ids from the storefront's filter menu (data-class). id 9 is
# Personal-Care (non-F&B) and is deliberately excluded.
_CATEGORIES = {
    1: "Wine",
    2: "Chocolate-Candies-Sweets",
    3: "Nuts-Dried-Fruit",
    4: "Beverages",
    5: "Frozen-Food",
    6: "Cereals-Noodles-Rice",
    7: "Oils-Canned-food-seasoning",
    8: "Biscuits-Snacks-Seaweed",
}


class BestmartHkSpider(scrapy.Spider):
    name = "bestmart_hk"
    allowed_domains = ["bestmart360.com"]
    currency = "HKD"
    language = "zh"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    async def start(self):
        for cat_id in _CATEGORIES:
            yield self._page_request(cat_id, page=1)

    def _page_request(self, cat_id, page):
        return scrapy.FormRequest(
            _LIST_API,
            formdata={
                "category_id": str(cat_id),
                "product_id": "",
                "searchtext": "",
                "manufacturer_id": "",
                "option_value_id": "",
                "page": str(page),
            },
            callback=self.parse_list,
            meta={"category_id": cat_id, "page": page},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    def parse_list(self, response):
        cat_id = response.meta["category_id"]
        page = response.meta["page"]
        slug = _CATEGORIES[cat_id]
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("bestmart_hk: non-JSON response cat=%s p%d", slug, page)
            return

        fragment = scrapy.Selector(text=payload.get("products") or "")
        scraped_at = datetime.now(timezone.utc).isoformat()
        count = 0
        for card in fragment.css("div.product_li"):
            name = card.css("div.txt::text").get()
            price_parts = card.css("div.new_price ::text").getall()
            price = re.sub(r"\s+", " ", "".join(price_parts)).strip()
            product_id = card.css("[data-product-id]::attr(data-product-id)").get()
            if not name or not price:
                continue
            name = name.strip()
            if not name:
                continue
            count += 1
            yield {
                "product_id": product_id,
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": slug,
                "url": f"{_BASE}/cat?product_id={product_id}"
                if product_id
                else response.url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info("bestmart_hk: category=%s page=%d products=%d", slug, page, count)
        if payload.get("more"):
            yield self._page_request(cat_id, page + 1)

    def errback(self, failure):
        logger.error(
            "bestmart_hk: request failed %s — %r", failure.request.url, failure.value
        )

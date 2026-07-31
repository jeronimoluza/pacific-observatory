"""
Spider for Lazada Philippines / LazMart (lazada.com.ph).

Lazada is a marketplace aggregator; its LazMart grocery channel resells
Puregold / Mercury Drug / Rose Pharmacy / TGP alongside third-party sellers.
Unlike lazada.vn, the .ph catalog AJAX endpoint answers unauthenticated
requests: GET /catalog/?ajax=true&q=<keyword>&page=<n> returns JSON with a
`mods.listItems` array (40 per page) carrying name, itemId, sku, price and
seller. This spider walks a fixed grocery/F&B keyword list, paginating each up
to a cap and deduping by itemId. channel=aggregator (multi-seller catalog).
"""

import json
import logging
from datetime import datetime, timezone
from urllib.parse import quote

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.lazada.com.ph"
_CATALOG = _BASE + "/catalog/"
_PAGE_SIZE = 40
_MAX_PAGES = 20

_KEYWORDS = [
    "rice",
    "cooking oil",
    "milk",
    "powdered milk",
    "coffee",
    "sugar",
    "flour",
    "canned tuna",
    "sardines",
    "corned beef",
    "instant noodles",
    "soy sauce",
    "vinegar",
    "biscuits",
    "chocolate",
    "eggs",
    "butter",
    "cheese",
    "juice",
    "bottled water",
]


class LazadaPhLazmartSpider(scrapy.Spider):
    name = "lazada_ph_lazmart"
    allowed_domains = ["lazada.com.ph"]
    currency = "PHP"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
        "DEFAULT_REQUEST_HEADERS": {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 "
                "Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_ids = set()

    def _page_request(self, keyword, page):
        url = f"{_CATALOG}?ajax=true&q={quote(keyword)}&page={page}"
        return scrapy.Request(
            url,
            callback=self.parse_page,
            meta={"keyword": keyword, "page": page},
        )

    async def start(self):
        for keyword in _KEYWORDS:
            yield self._page_request(keyword, 1)

    def parse_page(self, response):
        keyword = response.meta["keyword"]
        page = response.meta["page"]
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(
                "lazada_ph_lazmart: non-JSON response kw=%s p=%d", keyword, page
            )
            return

        items = (payload.get("mods") or {}).get("listItems") or []
        if not items:
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        for it in items:
            item_id = it.get("itemId")
            name = it.get("name")
            price = it.get("price")
            if not item_id or not name or not price:
                continue
            if item_id in self._seen_ids:
                continue
            self._seen_ids.add(item_id)

            product_url = it.get("productUrl")
            if product_url and product_url.startswith("//"):
                url = "https:" + product_url
            else:
                url = f"{_BASE}/products/-i{item_id}.html"

            yield {
                "product_id": str(it.get("sku") or item_id),
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": None,
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        total = int((payload.get("mainInfo") or {}).get("totalResults") or 0)
        max_page = min(_MAX_PAGES, -(-total // _PAGE_SIZE) if total else _MAX_PAGES)
        if page < max_page and len(items) >= _PAGE_SIZE:
            yield self._page_request(keyword, page + 1)

    def errback(self, failure):
        logger.error(
            "lazada_ph_lazmart: request failed %s — %r",
            failure.request.url,
            failure.value,
        )

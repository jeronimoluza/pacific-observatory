"""
Spider for MetroMart (Philippines) - metromart.com.

MetroMart is a grocery-delivery marketplace aggregating multiple wet-market /
farmers-market / sari-sari vendors (not a single retailer catalog). There is
no browsable full-catalog endpoint without an authenticated session + delivery
address, but the public keyword-search endpoint
(api.metromart.com/api/v1/search/grouped-shops-and-products) requires no auth
and returns full product records - including price - via a JSON:API `include=
products` sideload. This spider walks a fixed list of Filipino/English
keywords targeting specialty produce and dried-fish items that are thin on
other PH sources (tubers, dried/salted fish, tropical fruits).

`filter[shop.area.id]=214` pins results to the "Bel-Air" (Makati, NCR) default
area returned by /api/v1/areas/default - the same NCR scope as the existing
waltermart spider.

No breadcrumb/category is exposed on the product record (only an opaque
`aisle` relationship id that does not resolve via `include`), so `category`
is left null per convention rather than inferring it from the search keyword.
"""

import json
import logging
from datetime import datetime, timezone
from urllib.parse import quote

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://api.metromart.com"
_SEARCH = _BASE + "/api/v1/search/grouped-shops-and-products"
_AREA_ID = 214  # Bel-Air, Makati - default NCR area from /api/v1/areas/default
_GROUP_SIZE = 20
_PAGE_SIZE = 50

# Deep-leaf targets: tubers (01.1.7.5.x), dried/salted fish (01.1.3.5.1 /
# 01.1.3.2.x), tropical fruits (01.1.6.1.x). English synonyms included since
# MetroMart's search matches on the product name verbatim.
_KEYWORDS = [
    "kamote",
    "sweet potato",
    "kamoteng kahoy",
    "cassava",
    "gabi",
    "taro",
    "ube",
    "tuyo",
    "daing",
    "dilis",
    "tinapa",
    "smoked fish",
    "langka",
    "jackfruit",
    "rambutan",
    "lanzones",
    "calamansi",
]


class MetromartPhSpider(scrapy.Spider):
    name = "metromart_ph"
    allowed_domains = ["api.metromart.com"]
    currency = "PHP"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_ids = set()

    async def start(self):
        for keyword in _KEYWORDS:
            yield self._search_request(keyword)

    def _search_request(self, keyword):
        params = (
            f"fields%5Bshops%5D=name"
            f"&filter%5Bkeyword%5D={quote(keyword)}"
            f"&filter%5Bmatch-criteria%5D=text-start"
            f"&filter%5Bshop.area.id%5D={_AREA_ID}"
            f"&filter%5Bshop.status%5D=open%2Cclosed"
            f"&filter%5Bproduct.status%5D=available"
            f"&filter%5Bgroup-size%5D={_GROUP_SIZE}"
            f"&include=products"
            f"&page%5Bsize%5D={_PAGE_SIZE}"
            f"&page%5Bnumber%5D=1"
        )
        return scrapy.Request(
            f"{_SEARCH}?{params}",
            callback=self.parse_search,
            meta={"keyword": keyword},
            headers={"Accept": "application/json"},
        )

    def parse_search(self, response):
        keyword = response.meta["keyword"]
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("metromart_ph: non-JSON response for keyword=%s", keyword)
            return

        included = payload.get("included") or []
        products = [row for row in included if row.get("type") == "products"]

        scraped_at = datetime.now(timezone.utc).isoformat()
        new_count = 0
        for row in products:
            product_id = row.get("id")
            if product_id is None or product_id in self._seen_ids:
                continue
            self._seen_ids.add(product_id)

            attrs = row.get("attributes") or {}
            name = attrs.get("name")
            amount_cents = attrs.get("amount-in-cents")
            if not name or amount_cents is None:
                continue

            size = attrs.get("size")
            product_name = f"{name} ({size})" if size else name

            yield {
                "product_id": str(product_id),
                "product_name": product_name,
                "price": amount_cents / 100.0,
                "currency": self.currency,
                "category": None,
                "url": (row.get("links") or {}).get("self"),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
            new_count += 1

        logger.info(
            "metromart_ph: keyword=%s -> %d products (%d new)",
            keyword,
            len(products),
            new_count,
        )

    def errback(self, failure):
        logger.error(
            "metromart_ph: request failed %s — %r", failure.request.url, failure.value
        )

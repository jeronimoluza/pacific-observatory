"""
Spider for Woolworths New Zealand (https://www.woolworths.co.nz/) — formerly
Countdown. Full-catalog online supermarket; NZ's only online grocery source
in the repo (Pak'nSave / New World sit behind the Foodstuffs/Akamai stack and
are pre-listed as blocked in references/known_blockers.md).

Tier 1B (scrapy_api). The public `/api/v1/products?target=search` endpoint
(same one the site's own Vue front-end calls) returns full product JSON —
name, brand, price, pack size/unit, and a department breadcrumb — with no
auth. Plain curl gets a bare TCP reset (Akamai edge on the domain), but the
project's default RandomBrowserMiddleware (curl_cffi TLS impersonation,
already on globally at priority 725) gets a clean 200 through the same edge;
the only extra requirement is the Origin/Referer/x-requested-with header set
the real front-end sends — a bare API call without those headers 400s with
"Header is missing or is invalid."

Paginates each search term (~24 items/page) up to PAGE_CAP pages.
"""

import json
import logging

import scrapy

logger = logging.getLogger(__name__)


class WoolworthsNzSpider(scrapy.Spider):
    name = "woolworths_nz"
    allowed_domains = ["woolworths.co.nz"]
    currency = "NZD"

    API_URL = "https://www.woolworths.co.nz/api/v1/products"
    PAGE_CAP = 5  # ~24 items/page; caps runtime per term while still covering breadth

    # Search terms targeting deep F&B leaves currently at ZERO coverage for NZ:
    # fresh produce (01.1.6/01.1.7), fish/seafood (01.1.3), meat (01.1.2),
    # dairy (01.1.4) — plus bakery/pantry/beverages for basket breadth.
    SEARCH_TERMS = [
        # fresh produce
        "apple",
        "banana",
        "orange",
        "potato",
        "onion",
        "tomato",
        "carrot",
        "lettuce",
        "broccoli",
        "capsicum",
        "kumara",
        "avocado",
        "cucumber",
        "pumpkin",
        "grapes",
        "mandarin",
        "kiwifruit",
        "spinach",
        "mushroom",
        # meat
        "beef",
        "lamb",
        "chicken",
        "pork",
        "mince",
        "sausages",
        "bacon",
        # fish / seafood
        "fish",
        "salmon",
        "tuna",
        "prawns",
        "mussels",
        "hoki",
        # dairy / eggs
        "milk",
        "cheese",
        "yoghurt",
        "butter",
        "eggs",
        "cream",
        # bakery
        "bread",
        "rolls",
        "flour",
        # pantry / grocery
        "rice",
        "pasta",
        "sugar",
        "oil",
        "sauce",
        "cereal",
        "tea",
        "coffee",
        # beverages
        "juice",
        "soft drink",
        "water",
        "beer",
        "wine",
    ]

    _HEADERS = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://www.woolworths.co.nz",
        "Referer": "https://www.woolworths.co.nz/",
        "x-requested-with": "OnlineShopping.WebApp",
    }

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "RETRY_HTTP_CODES": [400, 403, 429, 500, 502, 503, 504, 408],
        "RETRY_TIMES": 4,
    }

    def _search_url(self, term, page):
        return f"{self.API_URL}?target=search&search={term}&page={page}"

    async def start(self):
        for term in self.SEARCH_TERMS:
            yield scrapy.Request(
                self._search_url(term, 1),
                headers=self._HEADERS,
                callback=self.parse_search,
                meta={"term": term, "page": 1},
                dont_filter=True,
            )

    def parse_search(self, response):
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"woolworths_nz: JSON decode failed for {response.url}")
            return

        products = payload.get("products") or {}
        items = products.get("items") or []
        total = products.get("totalItems") or 0

        term = response.meta["term"]
        page = response.meta["page"]
        logger.info(
            f"woolworths_nz: term={term} page={page} items={len(items)} total={total}"
        )

        for it in items:
            if it.get("type") != "Product":
                continue
            name = it.get("name")
            sku = it.get("sku")
            price_block = it.get("price") or {}
            price = price_block.get("salePrice") or price_block.get("originalPrice")
            if not name or price is None:
                continue

            departments = it.get("departments") or []
            category = departments[0].get("name") if departments else None

            size_block = it.get("size") or {}
            unit_size = size_block.get("volumeSize") or it.get("unit")

            yield {
                "product_id": sku,
                "product_name": name if not unit_size else f"{name} {unit_size}",
                "price": price,
                "currency": self.currency,
                "category": category,
                "url": f"https://www.woolworths.co.nz/shop/productdetails?stockcode={sku}"
                if sku
                else response.url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

        next_page = page + 1
        if items and next_page <= self.PAGE_CAP and (page * 24) < total:
            yield scrapy.Request(
                self._search_url(term, next_page),
                headers=self._HEADERS,
                callback=self.parse_search,
                meta={"term": term, "page": next_page},
                dont_filter=True,
            )

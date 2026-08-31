"""
Quidu (Ireland) — https://www.quidu.ie/.

Real-price aggregator (not a survey publisher): a Django REST Framework
backend, same-origin under www.quidu.ie, that republishes live per-store
shelf prices scraped from Aldi, Dunnes Stores, SuperValu and Tesco. Each
row's `product_info_url` points at the actual retailer product page.
Confirmed 2026-08-31: `GET /api/categories/` and `/api/supermarkets/` are
open with `Accept: application/json`. `/api/products/count/` reports
122,091 raw rows / 44,963 deduplicated products across 15 categories
(fruit & vegetables, meat & poultry, bakery, fish & seafood, chilled food,
food cupboard, frozen food, drinks, alcohol/beer/wine, plus non-food
household/toiletries/baby/pet). Food & beverage categories alone account
for ~95k of the 122k raw rows.

`GET /api/products/` REJECTS an empty or missing `search` (400 "Search
term is required.") -- there is no bare listing/browse endpoint, and
`category=` alone 400s too (search is mandatory; category can only narrow
an existing search). It is genuine tokenized full-text search over the
product `name` (stop words and single letters return near-zero rows), not
a substring match, so the catalog cannot be walked by iterating a-z.
Instead this spider walks a curated list of ~80 common grocery search
terms across every food/beverage category (fruit, veg, meat, fish, dairy,
bakery, store-cupboard staples, frozen, drinks, alcohol) and follows each
term's own `next` cursor to the end. This is a keyword-seeded partial
catalog walk, not the full 44,963-product catalog -- but every row is a
real retailer SKU with a live price and a working retailer URL, e.g.
`GET /api/products/?search=milk` returned 'SuperValu Organic Whole Milk
(1 L)' EUR 1.49 -> https://shop.supervalu.ie/sm/delivery/rsid/5550/...

Each product carries its own chain-prefixed `in_house_id` (e.g.
'S1475578000', 'T250004728'), used as `product_id` here; `url` is the
underlying retailer's own product page, so DuplicationPipeline's
url-based dedup naturally collapses re-hits across overlapping keywords.
"""

import logging
from datetime import datetime, timezone
from urllib.parse import urlencode

import scrapy

logger = logging.getLogger(__name__)

API_BASE = "https://www.quidu.ie/api/products/"

# Curated grocery keywords, grouped by category, biased toward food &
# beverage (the categories that hold ~95k of the site's 122k raw rows).
_KEYWORDS = [
    # fruit & vegetables
    "apple",
    "banana",
    "orange",
    "potato",
    "onion",
    "carrot",
    "tomato",
    "lettuce",
    "broccoli",
    "mushroom",
    "garlic",
    "grape",
    "lemon",
    "avocado",
    "pepper",
    "cucumber",
    "berries",
    # meat & poultry
    "chicken",
    "beef",
    "pork",
    "lamb",
    "turkey",
    "bacon",
    "sausage",
    "mince",
    "steak",
    "ham",
    # fish & seafood
    "salmon",
    "tuna",
    "cod",
    "prawns",
    "mackerel",
    "haddock",
    # bakery
    "bread",
    "roll",
    "bun",
    "baguette",
    "croissant",
    "cake",
    "muffin",
    "scone",
    "bagel",
    # chilled food
    "milk",
    "cheese",
    "yogurt",
    "butter",
    "cream",
    "eggs",
    "hummus",
    "pate",
    # food cupboard
    "pasta",
    "rice",
    "flour",
    "sugar",
    "cereal",
    "biscuit",
    "sauce",
    "soup",
    "beans",
    "oil",
    "vinegar",
    "honey",
    "jam",
    "spice",
    "tea",
    "coffee",
    "chocolate",
    "crisps",
    "nuts",
    "noodle",
    # frozen food
    "pizza",
    "chips",
    "ice cream",
    "peas",
    "waffle",
    # drinks
    "juice",
    "water",
    "cola",
    "lemonade",
    "cordial",
    "smoothie",
    "squash",
    # alcohol / beer & cider / wine
    "wine",
    "beer",
    "cider",
    "lager",
    "gin",
    "vodka",
    "whiskey",
    "prosecco",
    "rum",
]

_MAX_PAGES_PER_KEYWORD = 80


class QuiduIeSpider(scrapy.Spider):
    name = "quidu_ie"
    allowed_domains = ["www.quidu.ie"]
    currency = "EUR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for kw in _KEYWORDS:
            url = f"{API_BASE}?{urlencode({'search': kw})}"
            yield scrapy.Request(
                url,
                callback=self.parse,
                errback=self.errback,
                headers={"Accept": "application/json"},
                meta={"keyword": kw, "page": 1},
                dont_filter=True,
            )

    def parse(self, response):
        keyword = response.meta["keyword"]
        page = response.meta["page"]
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON from {response.url}")
            return

        results = data.get("results") or []
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for p in results:
            name = (p.get("name") or "").strip()
            price = p.get("price")
            url = p.get("product_info_url")
            in_house_id = p.get("in_house_id")
            if not name or price is None or not url or not in_house_id:
                continue
            n += 1
            categories = p.get("parent_categories") or []
            yield {
                "product_id": in_house_id,
                "product_name": name[:500],
                "category": " / ".join(categories) if categories else None,
                "price": str(price),
                "currency": self.currency,
                "available": (p.get("status") == "in_stock"),
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        logger.info(
            f"{self.name}: keyword={keyword!r} page={page} "
            f"got={n} count={data.get('count')}"
        )

        next_url = data.get("next")
        if next_url and page < _MAX_PAGES_PER_KEYWORD:
            yield scrapy.Request(
                next_url,
                callback=self.parse,
                errback=self.errback,
                headers={"Accept": "application/json"},
                meta={"keyword": keyword, "page": page + 1},
                dont_filter=True,
            )

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )

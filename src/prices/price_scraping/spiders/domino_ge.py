"""
Spider for Domino (Georgia) - domino.com.ge, a home-improvement/hardware/
appliances retailer (CS-Cart storefront).

Server-rendered category listing pages at /products/<department>/page-N/.
Each product card embeds a hidden analytics span with clean data attributes:
`data-cpga-pid` (numeric SKU), `data-cpga-prodname` (name),
`data-cpga-price` (decimal GEL), `data-cpga-href` (PDP url) - no separate
PDP fetch needed. Pagination is a path segment (`page-N/`); the page past
the last one 404s with zero cards (verified on climatic-equipments: page 20
= 200/48 items, page 21 = 404/0 items), so the spider stops there. The 14
top-level department pages (from the homepage nav) already aggregate every
descendant subcategory's products (verified: climatic-equipments spans 20
pages / ~950 items vs. its conditioners subcategory alone at 3 pages / ~140
items), so only those 14 are walked - no subcategory tree needed.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.domino.com.ge"

_DEPARTMENTS = [
    "საღებავები-და-ლაქები-ka",
    "სანტექნიკა-და-აქსესუარები-ka",
    "ხელსაწყოები",
    "auto-products",
    "building-materials",
    "climatic-equipments",
    "decorative-goods",
    "electrical-goods",
    "floor-coverings",
    "furniture",
    "gardening-and-horticulture",
    "home-appliances",
    "household-goods",
    "tile",
]

_MAX_PAGES = 60


class DominoGeSpider(scrapy.Spider):
    name = "domino_ge"
    allowed_domains = ["domino.com.ge"]
    currency = "GEL"
    language = "ka"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    async def start(self):
        for slug in _DEPARTMENTS:
            yield scrapy.Request(
                f"{_BASE}/products/{slug}/page-1/",
                callback=self.parse_list,
                cb_kwargs={"slug": slug, "page": 1},
            )

    def parse_list(self, response, slug, page):
        cards = response.css("span[data-cpga-pid]")
        if not cards:
            logger.info("domino_ge: %s page %d empty, stopping", slug, page)
            return

        for card in cards:
            pid = card.attrib.get("data-cpga-pid")
            name = card.attrib.get("data-cpga-prodname")
            price = card.attrib.get("data-cpga-price")
            url = card.attrib.get("data-cpga-href")
            if not (pid and name and price and url):
                continue
            try:
                price_str = f"{float(price):.2f}"
            except ValueError:
                continue
            yield {
                "product_id": pid,
                "product_name": name.strip()[:500],
                "category": slug,
                "price": price_str,
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        if page >= _MAX_PAGES:
            logger.warning("domino_ge: %s hit page cap %d", slug, _MAX_PAGES)
            return

        next_page = page + 1
        yield scrapy.Request(
            f"{_BASE}/products/{slug}/page-{next_page}/",
            callback=self.parse_list,
            cb_kwargs={"slug": slug, "page": next_page},
        )

"""
Spider for Fontana Pharmacy (Jamaica) -- https://fontanapharmacy.com/.

CS-Cart-flavored SSR storefront (product_images/ path layout). Category
pages carry two `<ul class="ProductList">` blocks: a homepage-style
"featured" `owl-carousel` slider (recommendation widget, would double-
count items already on the page) and the real category grid, plain
`<ul class="ProductList">` with no carousel classes -- the spider skips
the carousel and reads only the grid. `?page=N` pagination via the
`CategoryPagination` "Next »" link.

Re-verified live 2026-08-17: GET /categories/Beauty/ -> 200, 611KB, 36
main-grid products (42 minus 6 carousel) e.g. "Tampax Pearl Regular
Unscented Tampon" JMD 980.00. Currency JMD matches the shard and
countries.yaml.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_TOP_CATEGORIES = [
    "Baby-%26-Toddler",
    "Beauty",
    "Caregiver-Essentials",
    "ELECTRONICS",
    "GIFT",
    "Gift-Ideas",
    "Grocery",
    "Health",
    "Home",
    "PARTY-AND-SPECIAL-OCCASIONS",
    "Personal-Care",
    "SEASONAL",
    "STATIONERY",
    "School-%26-Office-Supplies-",
    "TOYS",
]
MAX_PAGES_PER_CATEGORY = 15


class FontanapharmacyJmSpider(scrapy.Spider):
    name = "fontanapharmacy_jm"
    allowed_domains = ["fontanapharmacy.com"]
    currency = "JMD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for slug in _TOP_CATEGORIES:
            yield scrapy.Request(
                f"https://fontanapharmacy.com/categories/{slug}/",
                callback=self.parse_category,
                meta={"slug": slug, "page": 1},
            )

    def parse_category(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        grid = response.css("ul.ProductList:not(.owl-carousel) li")
        for card in grid:
            item = self._item(card, slug)
            if item:
                yield item
        if grid and page < MAX_PAGES_PER_CATEGORY:
            next_href = response.css(
                "div.CategoryPagination div.FloatRight a::attr(href)"
            ).get()
            if next_href:
                yield scrapy.Request(
                    next_href,
                    callback=self.parse_category,
                    meta={"slug": slug, "page": page + 1},
                )

    def _item(self, card, slug: str):
        name = card.css("h1.item_title a::text").get()
        href = card.css("h1.item_title a::attr(href)").get()
        price_text = card.css(".ProductPriceRating em::text").get()
        product_id = card.css("a[data-productid]::attr(data-productid)").get()
        if not name or not href or not price_text:
            return None
        price = re.sub(r"[^\d.]", "", price_text.split("JMD")[0])
        if not price:
            return None
        return {
            "product_id": product_id or href.rstrip("/").rsplit("/", 1)[-1],
            "product_name": name.strip()[:500],
            "category": slug.replace("-%26-", " & ").replace("-", " "),
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": href,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

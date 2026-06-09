import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

PRICE_RE = re.compile(r"Ks([\d,]+)")

CATEGORY_ROOTS = [
    "https://www.seingayhar.com/beverages-en",
    "https://www.seingayhar.com/bakery-and-breads-en",
    "https://www.seingayhar.com/bean-and-nuts-en",
    "https://www.seingayhar.com/biscuit-en",
    "https://www.seingayhar.com/candy-and-jelly-en",
    "https://www.seingayhar.com/chocolate-en",
    "https://www.seingayhar.com/coffee-en",
    "https://www.seingayhar.com/condiment-en",
    "https://www.seingayhar.com/cooking-oil-en",
    "https://www.seingayhar.com/dairy-and-eggs-en",
    "https://www.seingayhar.com/dry-tea-en",
    "https://www.seingayhar.com/flour-sugar-and-salt-en",
    "https://www.seingayhar.com/frozen-food-en",
    "https://www.seingayhar.com/household-cleaning-en",
    "https://www.seingayhar.com/instant-noodles-en",
    "https://www.seingayhar.com/jam-honey-and-spread-en",
    "https://www.seingayhar.com/meat-and-seafood-en",
    "https://www.seingayhar.com/noodle-and-pasta-en",
    "https://www.seingayhar.com/personal-care-en",
    "https://www.seingayhar.com/rice-and-grains-en",
    "https://www.seingayhar.com/snacks-en",
    "https://www.seingayhar.com/soap-and-detergent-en",
    "https://www.seingayhar.com/vegetable-oils-en",
]


class SeingayharSpider(scrapy.Spider):
    name = "seingayhar"
    allowed_domains = ["seingayhar.com", "www.seingayhar.com"]
    currency = "MMK"
    language = "en"

    SELECTORS = {
        "product_name": "div.right-block h4 a::text",
        "price": "div.price span.price-new::text",
        "product_link": "div.right-block h4 a::attr(href)",
        "next_page": "ul.pagination li.active + li a::attr(href)",
    }

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 8,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 3,
    }

    def start_requests(self):
        for url in CATEGORY_ROOTS:
            yield scrapy.Request(
                url,
                callback=self.parse_listing,
                meta={"category": url.rsplit("/", 1)[-1]},
            )

    def parse_listing(self, response):
        category = response.meta.get("category", "")
        scraped_at = datetime.now(timezone.utc).isoformat()

        products = response.css("div.product-layout")
        for p in products:
            name = p.css(self.SELECTORS["product_name"]).get()
            if not name:
                continue
            price_raw = p.css(self.SELECTORS["price"]).get()
            if not price_raw:
                continue
            m = PRICE_RE.search(price_raw)
            if not m:
                continue
            href = p.css(self.SELECTORS["product_link"]).get() or ""
            product_id = href.rstrip("/").rsplit("/", 1)[-1] if href else None

            yield {
                "product_id": product_id,
                "product_name": name.strip()[:500],
                "category": category,
                "price": m.group(1).replace(",", ""),
                "currency": self.currency,
                "url": response.urljoin(href) if href else response.url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        next_href = response.css(self.SELECTORS["next_page"]).get()
        if next_href:
            yield scrapy.Request(
                response.urljoin(next_href),
                callback=self.parse_listing,
                meta={"category": category},
            )

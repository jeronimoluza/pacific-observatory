"""
Spider for Little Farms Singapore - https://www.littlefarms.com/
Magento (Adobe Commerce), server-rendered catalog HTML. Crawls the paginated
/groceries listing (?p=N) which spans the full catalog (produce, proteins,
dairy, pantry, frozen, ...); product cards on the listing page already carry
name, price, and SKU, so no per-PDP visit is needed.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://littlefarms.com"
LISTING_URL = f"{BASE_URL}/groceries"


class LittleFarmsSpider(scrapy.Spider):
    name = "little_farms"
    allowed_domains = ["littlefarms.com"]
    currency = "SGD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 8,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 4,
    }

    async def start(self):
        yield scrapy.Request(
            f"{LISTING_URL}?p=1", callback=self.parse_listing, meta={"page": 1}
        )

    def parse_listing(self, response):
        cards = response.css("div.product-item-info")
        if not cards:
            logger.debug(f"no product cards at {response.url}")
            return

        for card in cards:
            name = card.css("a.product-item-link::text").get()
            if not name:
                continue
            url = card.css("a.product-item-link::attr(href)").get()
            price = card.css("span.price-wrapper::attr(data-price-amount)").get()
            if not price:
                continue
            sku = card.css("form[data-product-sku]::attr(data-product-sku)").get()

            yield {
                "product_id": sku,
                "product_name": name.strip()[:500],
                "category": None,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        page = response.meta["page"]
        if page == 1:
            last_page = response.css(
                "div.products.wrapper.grid.products-grid::attr(last-page)"
            ).get()
            try:
                last_page = int(last_page)
            except (TypeError, ValueError):
                last_page = 1
            for next_page in range(2, last_page + 1):
                yield scrapy.Request(
                    f"{LISTING_URL}?p={next_page}",
                    callback=self.parse_listing,
                    meta={"page": next_page},
                )

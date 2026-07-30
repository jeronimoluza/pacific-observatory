"""
Spider for Goodees Market (Macau) - goodees.market.

Small Magento 2 boutique grocery/F&B store (European & Australian imports
plus a "Made in Macau" line). Category listing pages (e.g. /all.html) are
server-rendered with product links and names, but the price block on the
*listing* card is an empty JS placeholder (`data-role="priceBox"` with no
content) - price, SKU and product id only render on the product detail page
(PDP). The crawl is therefore two-hop: walk /all.html?p=N for product URLs
(catalog is small, ~5 pages), then fetch each PDP for name/price/sku.

Prices are in MOP (Macanese pataca, `$` symbol on-site); storefront language
is English despite Macau's Chinese/Portuguese context - product names
observed during probing were all English.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://goodees.market"
_START = f"{_BASE}/all.html"


class GoodeesMarketSpider(scrapy.Spider):
    name = "goodees_market"
    allowed_domains = ["goodees.market"]
    currency = "MOP"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    async def start(self):
        yield scrapy.Request(f"{_START}?p=1", callback=self.parse_list)

    def parse_list(self, response):
        links = response.css("a.product-item-link::attr(href)").getall()
        seen = set()
        for href in links:
            if href in seen:
                continue
            seen.add(href)
            yield scrapy.Request(href, callback=self.parse_pdp)

        next_href = response.css("li.pages-item-next a.next::attr(href)").get()
        if next_href:
            yield response.follow(next_href, callback=self.parse_list)

    def parse_pdp(self, response):
        name = response.css("h1.page-title span[itemprop='name']::text").get()
        if not name:
            return
        name = name.strip()
        if not name:
            return

        price = response.css(".price-box .price-wrapper::attr(data-price-amount)").get()
        if price is None:
            price_text = response.css(".price-box .price::text").get()
            price = price_text.strip().lstrip("$") if price_text else None
        if not price:
            return

        sku = response.css(".product.attribute.sku .value::text").get()
        product_id = response.css(
            ".price-box[data-product-id]::attr(data-product-id)"
        ).get()

        yield {
            "product_id": product_id or sku,
            "product_name": name,
            "price": price,
            "currency": self.currency,
            "category": None,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        logger.error(
            "goodees_market: request failed %s — %r", failure.request.url, failure.value
        )

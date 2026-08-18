"""
Spider for New Yaohan eStore (Macau) - estore.newyaohan.com, Supermarket
section.

Magento 2 department-store storefront (New Yaohan eStore serves the whole
store, not just groceries - only the "Supermarket" mega-menu branch is
seeded here). Category listing pages under
`/en/new-category/supermarket/<leaf>.html` are server-rendered, but most
leaf categories only carry a couple of product links directly on the page
(the rest render via a lazy widget) - the crawl walks every seeded leaf
category for whatever product links are present, then fetches each PDP for
name/price, which is where the reliable machine-readable price sits
(`span[data-price-type='finalPrice']`, the current/sale price - Magento
Luma always also renders an `oldPrice` span for items without a discount,
so `finalPrice` is the one to use unconditionally).

Prices are in MOP (confirmed via `data-price-amount` / on-page "MOP xxx.xx"
text, matches countries.yaml default for macao_sar_china). Plain HTML is
open to a bare curl (Tier 1A) - no Playwright needed despite the site also
running a Next.js shell for some marketing pages.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://estore.newyaohan.com"

_START_CATEGORIES = [
    "baby-kids-food",
    "baby-products",
    "breakfast-jam",
    "candies-snacks",
    "canned-dried-food",
    "drinks",
    "festival-gifts",
    "health-food-health-supplements",
    "noodles-pasta",
    "personal-care-products",
    "rice-cooking-oil",
    "seasoning",
    "tea-beverages-coffee",
    "wine-spirits",
]


class EstoreNewyaohanSpider(scrapy.Spider):
    name = "estore_newyaohan"
    allowed_domains = ["estore.newyaohan.com"]
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
        for slug in _START_CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/en/new-category/supermarket/{slug}.html",
                callback=self.parse_list,
            )

    def parse_list(self, response):
        links = response.css('a[href*="catalog/product/view"]::attr(href)').getall()
        seen = set()
        for href in links:
            if href in seen:
                continue
            seen.add(href)
            yield scrapy.Request(response.urljoin(href), callback=self.parse_pdp)

    def parse_pdp(self, response):
        name = response.css("span[data-ui-id='page-title-wrapper']::text").get()
        if not name:
            return
        name = name.strip()
        if not name:
            return

        price = response.css(
            "span[data-price-type='finalPrice']::attr(data-price-amount)"
        ).get()
        if not price:
            return

        product_id = None
        for token in response.url.split("/"):
            if token.isdigit():
                product_id = token
                break

        category = (
            " > ".join(
                response.css(
                    ".breadcrumbs .items li span[itemprop='name']::text"
                ).getall()[1:-1]
            )
            or None
        )

        yield {
            "product_id": product_id,
            "product_name": name,
            "price": price,
            "currency": self.currency,
            "category": category,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        logger.error(
            "estore_newyaohan: request failed %s — %r",
            failure.request.url,
            failure.value,
        )

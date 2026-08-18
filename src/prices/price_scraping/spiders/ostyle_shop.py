"""
Spider for Orange Lifestyle 橙式生活 (Macau) - ostyle-shop.com.

WooCommerce (Flatsome theme) local Macau online supermarket. Category
listing pages (e.g. /product-category/meat/pork/) are server-rendered with
product cards (`li.product a` -> PDP link) and standard WooCommerce
pagination (`nav.woocommerce-pagination a.next.page-numbers`), but price/
currency only render cleanly as machine-readable `itemprop` meta tags on
the PDP, so the crawl is two-hop like goodees_market.py: walk each seeded
top-level category for product URLs (parent category pages already carry
products tagged to their subcategories, e.g. a pork product also carries
`product_cat-meat`), then fetch each PDP for name/price.

Prices are in MOP - confirmed machine-readable via
`meta[itemprop='priceCurrency']` on the PDP (matches countries.yaml
default for macao_sar_china), not parsed from the on-screen "$" symbol.
The wp-json WooCommerce Store API (`/wp-json/wc/store/v1/products`) is
Cloudflare-challenged (403 "Attention Required"), but plain category/PDP
HTML is open to a bare curl - Tier 1A, no Playwright needed.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.ostyle-shop.com"

_START_CATEGORIES = [
    "meat",
    "seafood",
    "fruitcategory",
    "groceries",
    "drinks",
    "dailysupplies",
    "snacks",
    "hotpotfood",
]


class OstyleShopSpider(scrapy.Spider):
    name = "ostyle_shop"
    allowed_domains = ["ostyle-shop.com"]
    currency = "MOP"
    language = "zh"

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
                f"{_BASE}/product-category/{slug}/", callback=self.parse_list
            )

    def parse_list(self, response):
        links = response.css("div.product-small a::attr(href)").getall()
        seen = set()
        for href in links:
            if "/product/" not in href or href in seen:
                continue
            seen.add(href)
            yield scrapy.Request(href, callback=self.parse_pdp)

        next_href = response.css(
            "nav.woocommerce-pagination a.next.page-numbers::attr(href)"
        ).get()
        if next_href:
            yield response.follow(next_href, callback=self.parse_list)

    def parse_pdp(self, response):
        name = response.css("h1.product-title::text").get()
        if not name:
            name = response.css("meta[property='og:title']::attr(content)").get()
            if name:
                name = name.split(" - ")[0]
        if not name:
            return
        name = name.strip()
        if not name:
            return

        price = response.css("meta[itemprop='price']::attr(content)").get()
        if not price:
            return
        currency = response.css("meta[itemprop='priceCurrency']::attr(content)").get()

        product_id = None
        body_class = response.css("body::attr(class)").get() or ""
        for token in body_class.split():
            if token.startswith("postid-"):
                product_id = token.replace("postid-", "")
                break

        category = (
            " > ".join(
                response.css(
                    "nav.breadcrumb a::text, nav.breadcrumbs a::text"
                ).getall()[1:]
            )
            or None
        )

        yield {
            "product_id": product_id,
            "product_name": name,
            "price": price,
            "currency": currency or self.currency,
            "category": category,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        logger.error(
            "ostyle_shop: request failed %s — %r", failure.request.url, failure.value
        )

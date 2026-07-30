"""
Spider for Dury Dury (Malaysia fresh-durian specialty vendor, WooCommerce)
- https://durydury.com/

Narrow single-category source (fresh durian, various clones: Musang King,
Black Thorn, D24 Sultan, etc.) targeting COICOP 01.1.6.1 (tropical fruit) -
a deep leaf that is thin/absent across other onboarded MY grocery sources.
"""

import logging
import re

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

logger = logging.getLogger(__name__)

# Inline selectors (not registered in the shared selectors.py registry).
SELECTORS = {
    "product_name": [
        "h1.elementor-heading-title::text",
        "h1::text",
        "meta[property='og:title']::attr(content)",
    ],
    "product_id": [
        "link[rel='canonical']::attr(href)",
    ],
}

# Prices render server-side as entity-encoded "RM" + amount split across
# nested <bdi>/<span> nodes (WooCommerce Price-amount markup), e.g.
# <span class="price"><bdi><span class="woocommerce-Price-currencySymbol">RM</span>98.00</bdi></span>
# so pull the text nodes from the first `span.price` block rather than a
# single CSS text selector.
_PRICE_RE = re.compile(r"[\d,]+\.\d{2}")


def _extract(response, selectors):
    for sel in selectors:
        value = response.css(sel).get()
        if value:
            return value.strip()
    return None


def _extract_price(response):
    for price_block in response.css("span.price"):
        texts = "".join(price_block.css("::text").getall())
        match = _PRICE_RE.search(texts)
        if match:
            return match.group().replace(",", "")
    return None


class DuryduryMySpider(CrawlSpider):
    name = "durydury_my"
    allowed_domains = ["durydury.com"]
    start_urls = [
        "https://durydury.com/shop/",
    ]
    currency = "MYR"

    # Anchored to the un-prefixed path only - the site mirrors every page
    # under /zh/, /ms/, /zh_hk/ locale prefixes, which would otherwise
    # duplicate every product 3-4x under a different URL/language.
    rules = (
        Rule(
            LinkExtractor(allow=r"^https://durydury\.com/shop/?$"),
            follow=True,
        ),
        Rule(
            LinkExtractor(
                allow=r"^https://durydury\.com/product/[^/?#]+/?$",
                deny=r"(cart|checkout|my-account|add-to-cart)",
            ),
            callback="parse_product",
            follow=False,
        ),
    )

    def parse_product(self, response):
        product_name = _extract(response, SELECTORS["product_name"])
        price = _extract_price(response)
        product_id = _extract(response, SELECTORS["product_id"])

        if product_name and price:
            yield {
                "product_id": product_id,
                "product_name": product_name,
                "price": price,
                "currency": self.currency,
                "category": "Fresh durian",
                "url": response.url,
                "scraped_at": response.headers.get("Date", "").decode("utf-8"),
            }
            logger.info(f"Scraped product: {product_name}")
        else:
            logger.warning(f"Could not extract product data from {response.url}")

"""
Spider for Ayamkitafresh (Malaysia online wet-market grocer, Shopline platform)
- https://www.ayamkitafresh.com/

Scoped to fresh-produce / specialty collections (fruits, vegetables/tubers,
cooking oil, fresh + dried fish) rather than the full catalogue, to target
deep COICOP leaves (palm cooking oil, tropical fruit, tubers, fresh/dried
fish) that are thin across existing MY sources.
"""

import logging
import re

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

logger = logging.getLogger(__name__)

# Inline selectors (not registered in the shared selectors.py registry).
SELECTORS = {
    "product_name": [
        "h1[itemprop='name']::text",
        "meta[property='og:title']::attr(content)",
    ],
    "price": [
        "span#ProductPrice::attr(content)",
        "span.product-single__price::attr(content)",
        "span.money::text",
    ],
    "product_id": [
        "link[rel='canonical']::attr(href)",
    ],
}

# The site embeds a per-page analytics payload with a "category" key
# (e.g. `"category":"Sayur&quot;Karbohidrat"`) that is not reachable via
# a clean CSS selector. Extract it with a regex fallback instead of inventing
# a breadcrumb selector that doesn't exist on this theme's PDP.
_CATEGORY_RE = re.compile(r'"category":"([^"]*)"')


def _extract(response, selectors):
    for sel in selectors:
        value = response.css(sel).get()
        if value:
            return value.strip()
    return None


class AyamkitafreshMySpider(CrawlSpider):
    name = "ayamkitafresh_my"
    allowed_domains = ["ayamkitafresh.com", "www.ayamkitafresh.com"]
    start_urls = [
        "https://www.ayamkitafresh.com/collections/buah-buahan",  # tropical fruits
        "https://www.ayamkitafresh.com/collections/sayur-sayuran",  # veg / tubers
        "https://www.ayamkitafresh.com/collections/minyak-masak",  # cooking oil
        "https://www.ayamkitafresh.com/collections/fish",  # fresh fish
        "https://www.ayamkitafresh.com/collections/ikan-frozen",  # frozen fish/seafood
        "https://www.ayamkitafresh.com/collections/ikan-masin-1",  # salted/dried fish
    ]
    currency = "MYR"

    rules = (
        Rule(
            LinkExtractor(
                allow=r"/collections/(buah-buahan|sayur-sayuran|minyak-masak|fish|ikan-frozen|ikan-masin-1)(\?page=\d+)?$",
            ),
            follow=True,
        ),
        Rule(
            LinkExtractor(
                allow=r"/products/[^/?#]+",
                deny=r"(cart|checkout|account|/search)",
            ),
            callback="parse_product",
            follow=False,
        ),
    )

    def parse_product(self, response):
        product_name = _extract(response, SELECTORS["product_name"])
        price = _extract(response, SELECTORS["price"])
        product_id = _extract(response, SELECTORS["product_id"])

        category = None
        match = _CATEGORY_RE.search(response.text)
        if match:
            raw = match.group(1).replace("\\u0026quot;", " > ").replace("\\u0026", "&")
            category = raw.strip(" >") or None

        if product_name and price:
            yield {
                "product_id": product_id,
                "product_name": product_name,
                "price": price,
                "currency": self.currency,
                "category": category,
                "url": response.url,
                "scraped_at": response.headers.get("Date", "").decode("utf-8"),
            }
            logger.info(f"Scraped product: {product_name}")
        else:
            logger.warning(f"Could not extract product data from {response.url}")

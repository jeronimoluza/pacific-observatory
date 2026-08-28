"""
Spider for Azha Pasa (Bhutan supermarket) - https://www.azhapasa.com/

CrawlSpider Pattern A — server-rendered HTML. PDPs at /shop/product/<slug>.
"""

import logging
from typing import Iterator

import scrapy
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from price_scraping.utils import SelectorExtractor

from ..archived import row_from_meta, rows_from_jsonld

logger = logging.getLogger(__name__)


class AzhaPasaSpider(CrawlSpider):
    name = "azha_pasa"
    allowed_domains = ["azhapasa.com", "www.azhapasa.com"]
    start_urls = [
        "https://www.azhapasa.com/products",
        "https://www.azhapasa.com/deals",
    ]
    currency = "BTN"

    SELECTORS = {
        "product_name": [
            "h1.product-title::text",
            "h1.product-name::text",
            "h1[itemprop='name']::text",
            "meta[property='og:title']::attr(content)",
            "h1::text",
        ],
        "price": [
            "span.new-price::text",
            ".new-price::text",
            "div.product-price span.new-price::text",
            "span.product-price::text",
            "meta[property='product:price:amount']::attr(content)",
        ],
        "category": [
            "ol.breadcrumb li a::text",
            "div.breadcrumb a::text",
        ],
        "product_id": [
            "meta[property='product:retailer_item_id']::attr(content)",
            "span.sku::text",
        ],
    }

    rules = (
        Rule(
            LinkExtractor(
                allow=r"/shop/product/[a-z0-9\-]+$",
                deny=r"(cart|account|login|search|/category/|wishlist)",
            ),
            callback="parse_product",
            follow=True,
        ),
    )

    def parse_product(self, response):
        extractor = SelectorExtractor(response, logger)
        product_name = extractor.extract("product_name", self.SELECTORS["product_name"])
        price = extractor.extract("price", self.SELECTORS["price"])
        category = extractor.extract(
            "category", self.SELECTORS["category"], method="getall"
        )
        product_id = extractor.extract("product_id", self.SELECTORS["product_id"])

        if product_name and price:
            yield {
                "product_id": product_id,
                "product_name": product_name,
                "price": price,
                "currency": self.currency,
                "category": " > ".join(category) if category else None,
                "url": response.url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
        else:
            logger.warning(f"Could not extract product data from {response.url}")

    # ------------------------------------------------------------------
    # Crawl backfiller (prices/backfill.py's parse_html hook). Tries the
    # shared jsonld/meta tiers first, then falls back to the same bespoke
    # selectors the live parse uses (production-proven against this exact
    # /shop/product/<slug> template).
    # ------------------------------------------------------------------
    @classmethod
    def parse_html(cls, html_text: str, url: str) -> Iterator[dict]:
        """Parse one archived Azha Pasa PDP page."""
        rows = rows_from_jsonld(html_text, url)
        if not rows:
            row = row_from_meta(html_text, url)
            rows = [row] if row else []
        if rows:
            for row in rows:
                row.setdefault("currency", cls.currency)
                yield row
            return

        sel = scrapy.Selector(text=html_text)
        name = None
        for csel in cls.SELECTORS["product_name"]:
            name = sel.css(csel).get()
            if name and name.strip():
                name = name.strip()
                break
        if not name:
            return
        price = None
        for csel in cls.SELECTORS["price"]:
            price = sel.css(csel).get()
            if price and price.strip():
                price = price.strip()
                break
        if not price:
            return
        product_id = None
        for csel in cls.SELECTORS["product_id"]:
            product_id = sel.css(csel).get()
            if product_id and product_id.strip():
                product_id = product_id.strip()
                break
        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "price": price,
            "currency": cls.currency,
            "url": url,
        }

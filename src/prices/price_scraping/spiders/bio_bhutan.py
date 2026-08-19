"""
Spider for Bio Bhutan (organic natural products) - https://biobhutan.com/

CrawlSpider Pattern A — WooCommerce. PDPs at /product/<slug>/.
"""

import logging
from typing import Iterator

import scrapy
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from price_scraping.utils import SelectorExtractor

from ..archived import row_from_meta, rows_from_jsonld

logger = logging.getLogger(__name__)


class BioBhutanSpider(CrawlSpider):
    name = "bio_bhutan"
    allowed_domains = ["biobhutan.com"]
    start_urls = [
        "https://biobhutan.com/shop/",
        "https://biobhutan.com/product-category/herbal-teas/",
        "https://biobhutan.com/product-category/natural-handmade-soap-bar/",
        "https://biobhutan.com/product-category/non-wood-forest-products/",
        "https://biobhutan.com/product-category/organic-spices/",
        "https://biobhutan.com/product-category/pure-essential-oils-and-fragrances/",
    ]
    currency = "BTN"

    SELECTORS = {
        "product_name": [
            "h1.product_title.entry-title::text",
            "h1[itemprop='name']::text",
            "meta[property='og:title']::attr(content)",
            "h1::text",
        ],
        "price": [
            "p.price ins span.woocommerce-Price-amount bdi::text",
            "p.price span.woocommerce-Price-amount bdi::text",
            "div.summary p.price span.woocommerce-Price-amount::text",
            "meta[property='product:price:amount']::attr(content)",
        ],
        "category": [
            "nav.woocommerce-breadcrumb a::text",
        ],
        "product_id": [
            "span.sku::text",
            "meta[property='product:retailer_item_id']::attr(content)",
        ],
    }

    rules = (
        Rule(
            LinkExtractor(
                allow=r"/product/[a-z0-9\-]+/?$",
                deny=r"(cart|checkout|account|login|search|add-to-cart=|wp-admin|product-category)",
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
    # Crawl backfiller (prices/backfill.py's parse_html hook). Confirmed
    # live 2026-08-18 on 2 PDPs: this WooCommerce theme emits a standard
    # Product JSON-LD block, so the shared jsonld tier covers it. Falls
    # back to the same bespoke selectors the live parse uses, for archived
    # snapshots predating the JSON-LD plugin or on a theme swap.
    # ------------------------------------------------------------------
    @classmethod
    def parse_html(cls, html_text: str, url: str) -> Iterator[dict]:
        """Parse one archived Bio Bhutan PDP page."""
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

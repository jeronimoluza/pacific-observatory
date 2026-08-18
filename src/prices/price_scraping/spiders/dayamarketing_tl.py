"""
Spider for Daya Marketing (Timor-Leste) - www.dayamarketing.co

Distributor storefront (Dili) on Wix. Despite the "distribution/wholesale"
framing, the site is not brochure-only: it runs a real Wix Stores catalog
with per-product pages, each carrying a clean Schema.org Product JSON-LD
block (name, sku, offers.price, offers.priceCurrency) directly in the raw
server-rendered HTML -- Tier 1A, no JS execution needed. Catalog spans
imported beverages (beer, juice) and personal-care / cleaning goods sold in
wholesale-style pack sizes (e.g. "36-105ml"), consistent with a distributor
selling both to consumers and to retailers via the same webstore.

Currency: JSON-LD reports priceCurrency=USD, matching countries.yaml for
Timor-Leste -- set at the class level regardless (never parsed from a
symbol).

`/shop` uses Wix's client-side collection widget and yields no product
links via plain HTTP, so discovery crawls from both the homepage and
`/shop` (whose SSR shell still includes one batch of product-page links).
"""

import json
import logging

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

logger = logging.getLogger(__name__)


class DayamarketingTlSpider(CrawlSpider):
    name = "dayamarketing_tl"
    allowed_domains = ["dayamarketing.co"]
    start_urls = [
        "https://www.dayamarketing.co/",
        "https://www.dayamarketing.co/shop",
    ]
    currency = "USD"
    language = "en"

    rules = (
        Rule(
            LinkExtractor(
                allow=r"/product-page/[a-zA-Z0-9\-]+$",
                deny=r"(cart|checkout|account|login)",
            ),
            callback="parse_product",
            follow=True,
        ),
    )

    def parse_product(self, response):
        for raw in response.css('script[type="application/ld+json"]::text').getall():
            try:
                data = json.loads(raw)
            except (ValueError, TypeError):
                continue
            if data.get("@type") != "Product":
                continue

            offers = data.get("Offers") or data.get("offers") or {}
            product_name = (data.get("name") or "").strip()
            price = offers.get("price")
            if not (product_name and price):
                continue

            yield {
                "product_id": data.get("sku")
                or response.url.rstrip("/").rsplit("/", 1)[-1],
                "product_name": product_name,
                "price": str(price),
                "currency": offers.get("priceCurrency") or self.currency,
                "category": None,
                "url": response.url,
                "language": self.language,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
            logger.info(f"Scraped product: {product_name}")
            return

        logger.warning(f"Could not extract product data from {response.url}")

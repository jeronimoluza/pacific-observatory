"""
Spider for Farmer Joe Supermarket (Samoa) via SamoaMarket aggregator (Shopify).

Scoped to the /collections/farmer-joe-supermarket Shopify collection.
Currency: NZD as declared by SamoaMarket's og:price:currency meta tag.
NOTE: SamoaMarket aggregates Samoan retailers' inventory on a NZ-hosted
Shopify and labels prices NZD; the in-store Samoan prices may differ in
WST (Tala). Downstream FX conversion treats prices as NZD.
"""

import logging

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from price_scraping.utils import SelectorExtractor
from price_scraping.selectors import get_selectors

logger = logging.getLogger(__name__)


class FarmerJoeSpider(CrawlSpider):
    name = "farmer_joe"
    allowed_domains = ["samoamarket.com", "www.samoamarket.com"]
    start_urls = [
        "https://www.samoamarket.com/collections/farmer-joe-supermarket",
    ]
    currency = "NZD"

    SELECTORS = get_selectors("farmer_joe")

    rules = (
        Rule(
            LinkExtractor(
                allow=r"/collections/farmer-joe-supermarket(\?page=\d+)?$",
            ),
            follow=True,
        ),
        Rule(
            LinkExtractor(
                allow=r"/products/[^/?#]+",
                deny=r"(cart|checkout|account|/policies/|search\?)",
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
            "category", self.SELECTORS.get("category", []), method="getall"
        )
        product_id = extractor.extract(
            "product_id", self.SELECTORS.get("product_id", [])
        )

        if product_name and price:
            yield {
                "product_id": product_id,
                "product_name": product_name,
                "price": price,
                "currency": self.currency,
                "category": " > ".join(category) if category else None,
                "url": response.url,
                "scraped_at": response.headers.get("Date", "").decode("utf-8"),
            }
            logger.info(f"Scraped product: {product_name}")
        else:
            logger.warning(f"Could not extract product data from {response.url}")

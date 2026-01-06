"""
Item definitions for the price_scraping project.
Defines the structure of scraped data.
"""

import scrapy


class ProductItem(scrapy.Item):
    """
    Represents a product scraped from an e-commerce site.
    """

    product_id = scrapy.Field()
    product_name = scrapy.Field()
    price = scrapy.Field()
    currency = scrapy.Field()
    category = scrapy.Field()
    url = scrapy.Field()
    url_hash = scrapy.Field()  # For deduplication
    scraped_at = scrapy.Field()
    version_hash = scrapy.Field()  # For tracking HTML changes

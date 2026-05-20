"""
Item definitions for the price_scraping project.
Defines the structure of scraped data.
"""

import scrapy


class ProductItem(scrapy.Item):
    """
    Represents a product scraped from an e-commerce site.

    Retailer spiders set the core fields. Aggregator spiders (livingcost,
    mylifeelsewhere, expatistan) emit city-aggregate medians and also set the
    optional aggregator-only fields below; retailers leave them unset and the
    JSONL output omits them.
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

    # Aggregator-only optional fields (city-aggregate sources, Numbeo-style).
    price_usd = scrapy.Field()
    city = scrapy.Field()
    source_date_label = scrapy.Field()
    n_observations = scrapy.Field()
    price_raw = scrapy.Field()

"""Maldives-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MaldivesToddySpider(ShopifyBaseSpider):
    name = "maldives_toddy"
    allowed_domains = ["weartoddy.com"]
    base_url = "https://weartoddy.com"
    currency = "MVR"
    language = "en"

    def _items(self, product):
        for item in super()._items(product):
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            item["country"] = 'Maldives'
            item["sector"] = "consumer_goods"
            yield item

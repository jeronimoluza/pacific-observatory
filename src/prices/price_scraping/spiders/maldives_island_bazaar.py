"""Maldives-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MaldivesIslandBazaarSpider(ShopifyBaseSpider):
    name = "maldives_island_bazaar"
    allowed_domains = ["island-bazaar.com"]
    base_url = "https://island-bazaar.com"
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

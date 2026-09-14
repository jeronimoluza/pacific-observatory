"""Maldives-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MaldivesSoneeSportsSpider(ShopifyBaseSpider):
    name = "maldives_sonee_sports"
    allowed_domains = ["soneesports.com"]
    base_url = "https://soneesports.com"
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

"""Timor-Leste-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class TimorLesteGybseeSpider(ShopifyBaseSpider):
    name = "timor_leste_gybsee"
    allowed_domains = ["gybsee.com"]
    base_url = "https://gybsee.com"
    currency = "USD"
    language = "id"

    def _items(self, product):
        for item in super()._items(product):
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            item["country"] = 'Timor-Leste'
            item["sector"] = "consumer_goods"
            yield item

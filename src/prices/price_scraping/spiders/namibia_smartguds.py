"""Namibia-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class NamibiaSmartgudsSpider(ShopifyBaseSpider):
    name = "namibia_smartguds"
    allowed_domains = ["www.smartguds.com"]
    base_url = "https://www.smartguds.com"
    currency = "ZAR"
    language = "en"


    def _items(self, product):
        for item in super()._items(product):
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            item["country"] = 'Namibia'
            item["sector"] = "consumer_goods"
            yield item

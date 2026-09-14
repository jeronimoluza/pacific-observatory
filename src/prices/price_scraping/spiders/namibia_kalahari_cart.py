"""Namibia-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class NamibiaKalahariCartSpider(ShopifyBaseSpider):
    name = "namibia_kalahari_cart"
    allowed_domains = ["kalaharicart.store"]
    base_url = "https://kalaharicart.store"
    currency = "NAD"
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

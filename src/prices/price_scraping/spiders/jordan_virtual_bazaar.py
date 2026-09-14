"""Virtual Bazaar Jordan's complete public Shopify catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class JordanVirtualBazaarSpider(ShopifyBaseSpider):
    name = "jordan_virtual_bazaar"
    allowed_domains = ["virtual-bazaar.com"]
    base_url = "https://virtual-bazaar.com"
    currency = "USD"
    language = "en"

    def _items(self, product):
        for item in super()._items(product):
            item["country"] = "Jordan"
            item["sector"] = "consumer_goods"
            yield item

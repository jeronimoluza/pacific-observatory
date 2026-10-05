"""Egypt-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class EgyptZacshopSpider(ShopifyBaseSpider):
    name = "egypt_zacshop"
    allowed_domains = ["zacshop.com"]
    base_url = "https://zacshop.com"
    currency = "EGP"
    language = "ar"


    def _items(self, product):
        for item in super()._items(product):
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            item["country"] = 'Egypt'
            item["sector"] = "consumer_goods"
            yield item

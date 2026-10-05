"""Mexico-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MexicoTogaPerfumeriaSpider(ShopifyBaseSpider):
    name = "mexico_toga_perfumeria"
    allowed_domains = ["togaperfumeria.com"]
    base_url = "https://togaperfumeria.com"
    currency = "MXN"
    language = "es"


    def _items(self, product):
        for item in super()._items(product):
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            item["country"] = 'Mexico'
            item["sector"] = "consumer_goods"
            yield item

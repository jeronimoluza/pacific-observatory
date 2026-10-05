"""Panama-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class PanamaFelixSpider(ShopifyBaseSpider):
    name = "panama_felix"
    allowed_domains = ["felix.com.pa"]
    base_url = "https://felix.com.pa"
    currency = "USD"
    language = "es"


    def _items(self, product):
        for item in super()._items(product):
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            item["country"] = 'Panama'
            item["sector"] = "consumer_goods"
            yield item

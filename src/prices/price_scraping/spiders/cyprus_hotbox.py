"""Cyprus-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class CyprusHotboxSpider(ShopifyBaseSpider):
    name = "cyprus_hotbox"
    allowed_domains = ["hotboxcy.com"]
    base_url = "https://hotboxcy.com"
    currency = "EUR"
    language = "en"


    def _items(self, product):
        for item in super()._items(product):
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            item["country"] = 'Cyprus'
            item["sector"] = "consumer_goods"
            yield item

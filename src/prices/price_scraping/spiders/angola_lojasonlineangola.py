"""Angola-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class AngolaLojasonlineangolaSpider(ShopifyBaseSpider):
    name = "angola_lojasonlineangola"
    allowed_domains = ["lojasonlineangola.com"]
    base_url = "https://lojasonlineangola.com"
    currency = "AOA"
    language = "pt"

    def _items(self, product):
        for item in super()._items(product):
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            item["country"] = 'Angola'
            item["sector"] = "consumer_goods"
            yield item

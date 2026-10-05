"""Malta-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MaltaMeatsAndEatsSpider(ShopifyBaseSpider):
    name = "malta_meats_and_eats"
    allowed_domains = ["meatsandeats.com.mt"]
    base_url = "https://meatsandeats.com.mt"
    currency = "EUR"
    language = "en"


    def _items(self, product):
        for item in super()._items(product):
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            item["country"] = 'Malta'
            item["sector"] = "consumer_goods"
            yield item

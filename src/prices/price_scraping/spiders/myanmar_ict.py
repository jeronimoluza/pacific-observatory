"""Myanmar-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MyanmarIctSpider(ShopifyBaseSpider):
    name = "myanmar_ict"
    allowed_domains = ["ict.com.mm"]
    base_url = "https://ict.com.mm"
    currency = "MMK"
    language = "en"


    def _items(self, product):
        for item in super()._items(product):
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            item["country"] = 'Myanmar'
            item["sector"] = "consumer_goods"
            yield item

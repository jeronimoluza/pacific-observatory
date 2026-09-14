"""Sri Lanka-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class SriLankaPetmartSpider(ShopifyBaseSpider):
    name = "sri_lanka_petmart"
    allowed_domains = ["petmart.lk"]
    base_url = "https://petmart.lk"
    currency = "LKR"
    language = "en"

    def _items(self, product):
        for item in super()._items(product):
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            item["country"] = 'Sri Lanka'
            item["sector"] = "consumer_goods"
            yield item

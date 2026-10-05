"""Sri Lanka-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class SriLankaFinezSpider(ShopifyBaseSpider):
    name = "sri_lanka_finez"
    allowed_domains = ["finez.lk"]
    base_url = "https://finez.lk"
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

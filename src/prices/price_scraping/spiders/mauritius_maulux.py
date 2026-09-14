"""Mauritius-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MauritiusMauluxSpider(ShopifyBaseSpider):
    name = "mauritius_maulux"
    allowed_domains = ["maulux.mu"]
    base_url = "https://maulux.mu"
    currency = "MUR"
    language = "en"


    def _items(self, product):
        for item in super()._items(product):
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            item["country"] = 'Mauritius'
            item["sector"] = "consumer_goods"
            yield item

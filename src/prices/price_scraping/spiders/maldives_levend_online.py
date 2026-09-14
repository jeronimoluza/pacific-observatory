"""Maldives-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MaldivesLevendOnlineSpider(ShopifyBaseSpider):
    name = "maldives_levend_online"
    allowed_domains = ["levendonline.com"]
    base_url = "https://levendonline.com"
    currency = "MVR"
    language = "en"

    def _items(self, product):
        for item in super()._items(product):
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            item["country"] = 'Maldives'
            item["sector"] = "consumer_goods"
            yield item

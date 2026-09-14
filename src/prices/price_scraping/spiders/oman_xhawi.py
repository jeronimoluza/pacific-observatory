"""Oman-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class OmanXhawiSpider(ShopifyBaseSpider):
    name = "oman_xhawi"
    allowed_domains = ["www.xhawi.com"]
    base_url = "https://www.xhawi.com"
    currency = "OMR"
    language = "en"


    def _items(self, product):
        for item in super()._items(product):
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            item["country"] = 'Oman'
            item["sector"] = "consumer_goods"
            yield item

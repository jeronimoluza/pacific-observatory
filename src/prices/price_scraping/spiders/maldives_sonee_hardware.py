"""Maldives-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MaldivesSoneeHardwareSpider(ShopifyBaseSpider):
    name = "maldives_sonee_hardware"
    allowed_domains = ["sonee.com.mv"]
    base_url = "https://sonee.com.mv"
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

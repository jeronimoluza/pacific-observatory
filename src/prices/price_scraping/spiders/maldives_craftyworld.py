"""Maldives-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class MaldivesCraftyworldSpider(WooBaseSpider):
    name = "maldives_craftyworld"
    allowed_domains = ["craftyworld.mv"]
    BASE_URL = "https://craftyworld.mv/wp-json/wc/store/v1/products"
    currency = "MVR"
    language = "en"


    def _item(self, product):
        item = super()._item(product)
        if not item or not item.get("product_name"):
            return None
        try:
            if float(item["price"]) <= 0:
                return None
        except (TypeError, ValueError):
            return None
        item["country"] = 'Maldives'
        item["sector"] = "consumer_goods"
        return item

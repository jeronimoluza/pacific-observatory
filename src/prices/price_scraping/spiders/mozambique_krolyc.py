"""Mozambique-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class MozambiqueKrolycSpider(WooBaseSpider):
    name = "mozambique_krolyc"
    allowed_domains = ["krolyc.co.mz"]
    BASE_URL = "https://krolyc.co.mz/wp-json/wc/store/v1/products"
    currency = "MZN"
    language = "pt"

    def _item(self, product):
        item = super()._item(product)
        if not item or not item.get("product_name"):
            return None
        try:
            if float(item["price"]) <= 0:
                return None
        except (TypeError, ValueError):
            return None
        item["country"] = 'Mozambique'
        item["sector"] = "consumer_goods"
        return item

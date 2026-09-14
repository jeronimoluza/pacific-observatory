"""Gambia-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class GambiaSassGroupSpider(WooBaseSpider):
    name = "gambia_sass_group"
    allowed_domains = ["sassgroupgm.com"]
    BASE_URL = "https://sassgroupgm.com/wp-json/wc/store/v1/products"
    currency = "GMD"
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
        item["country"] = 'Gambia'
        item["sector"] = "consumer_goods"
        return item

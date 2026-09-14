"""Bahrain-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class BahrainAlibakshSpider(WooBaseSpider):
    name = "bahrain_alibaksh"
    allowed_domains = ["alibaksh.com"]
    BASE_URL = "https://alibaksh.com/wp-json/wc/store/v1/products"
    currency = "BHD"
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
        item["country"] = 'Bahrain'
        item["sector"] = "consumer_goods"
        return item

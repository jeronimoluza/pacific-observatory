"""Guyana-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class GuyanaFizuroSpider(WooBaseSpider):
    name = "guyana_fizuro"
    allowed_domains = ["fizuro.com"]
    BASE_URL = "https://fizuro.com/wp-json/wc/store/v1/products"
    currency = "GYD"
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
        item["country"] = 'Guyana'
        item["sector"] = "consumer_goods"
        return item

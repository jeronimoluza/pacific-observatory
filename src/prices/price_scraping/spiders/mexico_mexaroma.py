"""Mexico-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class MexicoMexaromaSpider(WooBaseSpider):
    name = "mexico_mexaroma"
    allowed_domains = ["mexaromastore.com"]
    BASE_URL = "https://mexaromastore.com/wp-json/wc/store/v1/products"
    currency = "MXN"
    language = "es"


    def _item(self, product):
        item = super()._item(product)
        if not item or not item.get("product_name"):
            return None
        try:
            if float(item["price"]) <= 0:
                return None
        except (TypeError, ValueError):
            return None
        item["country"] = 'Mexico'
        item["sector"] = "consumer_goods"
        return item

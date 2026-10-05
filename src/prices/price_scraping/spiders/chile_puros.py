"""Chile-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class ChilePurosSpider(WooBaseSpider):
    name = "chile_puros"
    allowed_domains = ["www.puros.cl"]
    BASE_URL = "https://www.puros.cl/wp-json/wc/store/v1/products"
    currency = "CLP"
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
        item["country"] = 'Chile'
        item["sector"] = "consumer_goods"
        return item

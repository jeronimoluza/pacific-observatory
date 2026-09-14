"""Peru-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class PeruFarmaciasPeruSpider(WooBaseSpider):
    name = "peru_farmacias_peru"
    allowed_domains = ["www.farmaciasperu.pe"]
    BASE_URL = "https://www.farmaciasperu.pe/wp-json/wc/store/v1/products"
    currency = "PEN"
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
        item["country"] = 'Peru'
        item["sector"] = "consumer_goods"
        return item

"""Sri Lanka-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class SriLankaPrimehomeSpider(WooBaseSpider):
    name = "sri_lanka_primehome"
    allowed_domains = ["primehome.lk"]
    BASE_URL = "https://primehome.lk/wp-json/wc/store/v1/products"
    currency = "LKR"
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
        item["country"] = 'Sri Lanka'
        item["sector"] = "consumer_goods"
        return item

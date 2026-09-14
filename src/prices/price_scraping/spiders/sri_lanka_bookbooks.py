"""Sri Lanka-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class SriLankaBookbooksSpider(WooBaseSpider):
    name = "sri_lanka_bookbooks"
    allowed_domains = ["bookbooks.lk"]
    BASE_URL = "https://bookbooks.lk/wp-json/wc/store/v1/products"
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

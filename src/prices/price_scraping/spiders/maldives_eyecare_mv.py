"""Maldives-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class MaldivesEyecareMvSpider(WooBaseSpider):
    name = "maldives_eyecare_mv"
    allowed_domains = ["eyecare.mv"]
    BASE_URL = "https://eyecare.mv/wp-json/wc/store/v1/products"
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

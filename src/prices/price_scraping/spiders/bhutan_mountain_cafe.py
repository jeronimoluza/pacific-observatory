"""Bhutan-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class BhutanMountainCafeSpider(WooBaseSpider):
    name = "bhutan_mountain_cafe"
    allowed_domains = ["mountaincafe.bt"]
    BASE_URL = "https://mountaincafe.bt/wp-json/wc/store/v1/products"
    currency = "BTN"
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
        item["country"] = 'Bhutan'
        item["sector"] = "consumer_goods"
        return item

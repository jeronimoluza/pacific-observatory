"""Canada-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class CanadaMohawkSmokeSpider(WooBaseSpider):
    name = "canada_mohawk_smoke"
    allowed_domains = ["mohawksmoke.com"]
    BASE_URL = "https://mohawksmoke.com/wp-json/wc/store/v1/products"
    currency = "CAD"
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
        item["country"] = 'Canada'
        item["sector"] = "consumer_goods"
        return item

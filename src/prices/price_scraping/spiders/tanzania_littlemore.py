"""Tanzania-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class TanzaniaLittlemoreSpider(WooBaseSpider):
    name = "tanzania_littlemore"
    allowed_domains = ["littlemore.co.tz"]
    BASE_URL = "https://littlemore.co.tz/wp-json/wc/store/v1/products"
    currency = "TZS"
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
        item["country"] = 'Tanzania'
        item["sector"] = "consumer_goods"
        return item

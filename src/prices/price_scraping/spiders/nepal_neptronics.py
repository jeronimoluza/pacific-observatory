"""Nepal-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class NepalNeptronicsSpider(WooBaseSpider):
    name = "nepal_neptronics"
    allowed_domains = ["neptronics.com"]
    BASE_URL = "https://neptronics.com/wp-json/wc/store/v1/products"
    currency = "NPR"
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
        item["country"] = 'Nepal'
        item["sector"] = "consumer_goods"
        return item

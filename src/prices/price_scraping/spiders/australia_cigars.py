"""Australia-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class AustraliaCigarsSpider(WooBaseSpider):
    name = "australia_cigars"
    allowed_domains = ["www.cigars.com.au"]
    BASE_URL = "https://www.cigars.com.au/wp-json/wc/store/v1/products"
    currency = "AUD"
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
        item["country"] = 'Australia'
        item["sector"] = "consumer_goods"
        return item

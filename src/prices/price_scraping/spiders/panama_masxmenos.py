"""Panama-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class PanamaMasxmenosSpider(WooBaseSpider):
    name = "panama_masxmenos"
    allowed_domains = ["masxmenospanama.com"]
    BASE_URL = "https://masxmenospanama.com/wp-json/wc/store/v1/products"
    currency = "USD"
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
        item["country"] = 'Panama'
        item["sector"] = "consumer_goods"
        return item

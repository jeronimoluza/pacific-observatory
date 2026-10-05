"""Iraq-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class IraqNaramSpider(WooBaseSpider):
    name = "iraq_naram"
    allowed_domains = ["naram.com"]
    BASE_URL = "https://naram.com/wp-json/wc/store/v1/products"
    currency = "IQD"
    language = "ar"


    def _item(self, product):
        item = super()._item(product)
        if not item or not item.get("product_name"):
            return None
        try:
            if float(item["price"]) <= 0:
                return None
        except (TypeError, ValueError):
            return None
        item["country"] = 'Iraq'
        item["sector"] = "consumer_goods"
        return item

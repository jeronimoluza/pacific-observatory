"""Nicaragua-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class NicaraguaSmartpriceSpider(WooBaseSpider):
    name = "nicaragua_smartprice"
    allowed_domains = ["smartprice.com.ni"]
    BASE_URL = "https://smartprice.com.ni/wp-json/wc/store/v1/products"
    currency = "NIO"
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
        item["country"] = 'Nicaragua'
        item["sector"] = "consumer_goods"
        return item

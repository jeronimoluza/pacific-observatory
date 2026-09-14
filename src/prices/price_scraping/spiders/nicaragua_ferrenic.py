"""Nicaragua-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class NicaraguaFerrenicSpider(WooBaseSpider):
    name = "nicaragua_ferrenic"
    allowed_domains = ["ferrenic.com"]
    BASE_URL = "https://ferrenic.com/wp-json/wc/store/v1/products"
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

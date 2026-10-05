"""Pakistan-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class PakistanBookshopSpider(WooBaseSpider):
    name = "pakistan_bookshop"
    allowed_domains = ["bookshop.com.pk"]
    BASE_URL = "https://bookshop.com.pk/wp-json/wc/store/v1/products"
    currency = "PKR"
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
        item["country"] = 'Pakistan'
        item["sector"] = "consumer_goods"
        return item

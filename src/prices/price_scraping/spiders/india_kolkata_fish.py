"""India-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class IndiaKolkataFishSpider(WooBaseSpider):
    name = "india_kolkata_fish"
    allowed_domains = ["kolkatafish.com"]
    BASE_URL = "https://kolkatafish.com/wp-json/wc/store/v1/products"
    currency = "INR"
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
        item["country"] = 'India'
        item["sector"] = "consumer_goods"
        return item

"""India-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class IndiaKrishidharaSpider(WooBaseSpider):
    name = "india_krishidhara"
    allowed_domains = ["krishidhara.com"]
    BASE_URL = "https://krishidhara.com/wp-json/wc/store/v1/products"
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

"""Guinea-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class GuineaEtsralfSpider(WooBaseSpider):
    name = "guinea_etsralf"
    allowed_domains = ["etsralf.com"]
    BASE_URL = "https://etsralf.com/wp-json/wc/store/v1/products"
    currency = "GNF"
    language = "fr"


    def _item(self, product):
        item = super()._item(product)
        if not item or not item.get("product_name"):
            return None
        try:
            if float(item["price"]) <= 0:
                return None
        except (TypeError, ValueError):
            return None
        item["country"] = 'Guinea'
        item["sector"] = "consumer_goods"
        return item

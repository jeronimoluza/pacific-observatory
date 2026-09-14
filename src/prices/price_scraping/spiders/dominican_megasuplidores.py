"""Dominican Republic-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class DominicanMegasuplidoresSpider(WooBaseSpider):
    name = "dominican_megasuplidores"
    allowed_domains = ["megasuplidores.com.do"]
    BASE_URL = "https://megasuplidores.com.do/wp-json/wc/store/v1/products"
    currency = "DOP"
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
        item["country"] = 'Dominican Republic'
        item["sector"] = "consumer_goods"
        return item

"""New Caledonia-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class NewCaledoniaShanaNcSpider(WooBaseSpider):
    name = "new_caledonia_shana_nc"
    allowed_domains = ["shana.nc"]
    BASE_URL = "https://shana.nc/wp-json/wc/store/v1/products"
    currency = "XPF"
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
        item["country"] = 'New Caledonia'
        item["sector"] = "consumer_goods"
        return item

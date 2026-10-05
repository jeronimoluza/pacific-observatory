"""Ukraine-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class UkraineDoSmakuUaSpider(WooBaseSpider):
    name = "ukraine_do_smaku_ua"
    allowed_domains = ["do-smaku.com.ua"]
    BASE_URL = "https://do-smaku.com.ua/wp-json/wc/store/v1/products"
    currency = "UAH"
    language = "uk"

    def _item(self, product):
        item = super()._item(product)
        if not item or not item.get("product_name"):
            return None
        try:
            if float(item["price"]) <= 0:
                return None
        except (TypeError, ValueError):
            return None
        item["country"] = 'Ukraine'
        item["sector"] = "consumer_goods"
        return item

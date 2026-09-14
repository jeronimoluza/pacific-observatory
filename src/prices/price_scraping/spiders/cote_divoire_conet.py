"""Cote d'Ivoire-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class CoteDivoireConetSpider(WooBaseSpider):
    name = "cote_divoire_conet"
    allowed_domains = ["conet.ci"]
    BASE_URL = "https://conet.ci/wp-json/wc/store/v1/products"
    currency = "XOF"
    language = "fr"
    PER_PAGE = 10
    FORCE_CURRENCY = "XOF"



    def _item(self, product):
        item = super()._item(product)
        if not item or not item.get("product_name"):
            return None
        try:
            if float(item["price"]) <= 0:
                return None
        except (TypeError, ValueError):
            return None
        item["country"] = "Cote d'Ivoire"
        item["sector"] = "consumer_goods"
        return item

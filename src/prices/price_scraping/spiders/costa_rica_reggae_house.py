"""Costa Rica-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class CostaRicaReggaeHouseSpider(WooBaseSpider):
    name = "costa_rica_reggae_house"
    allowed_domains = ["reggae.house"]
    BASE_URL = "https://reggae.house/wp-json/wc/store/v1/products"
    currency = "CRC"
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
        item["country"] = 'Costa Rica'
        item["sector"] = "consumer_goods"
        return item

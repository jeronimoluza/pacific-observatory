"""Guatemala-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class GuatemalaMarketGtSpider(WooBaseSpider):
    name = "guatemala_market_gt"
    allowed_domains = ["market.gt"]
    BASE_URL = "https://market.gt/wp-json/wc/store/v1/products"
    currency = "GTQ"
    language = "es"
    PER_PAGE = 10



    def _item(self, product):
        item = super()._item(product)
        if not item or not item.get("product_name"):
            return None
        try:
            if float(item["price"]) <= 0:
                return None
        except (TypeError, ValueError):
            return None
        item["country"] = 'Guatemala'
        item["sector"] = "consumer_goods"
        return item

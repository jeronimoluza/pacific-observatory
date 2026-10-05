"""Chile-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class ChileTabaqueriaSpider(ShopifyBaseSpider):
    name = "chile_tabaqueria"
    allowed_domains = ["tabaqueria.cl"]
    base_url = "https://tabaqueria.cl"
    currency = "CLP"
    language = "es"


    def _items(self, product):
        for item in super()._items(product):
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            item["country"] = 'Chile'
            item["sector"] = "consumer_goods"
            yield item

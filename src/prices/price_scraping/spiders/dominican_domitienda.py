"""Dominican Republic-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class DominicanDomitiendaSpider(ShopifyBaseSpider):
    name = "dominican_domitienda"
    allowed_domains = ["domitiendashop.com"]
    base_url = "https://domitiendashop.com"
    currency = "DOP"
    language = "es"


    def _items(self, product):
        for item in super()._items(product):
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            item["country"] = 'Dominican Republic'
            item["sector"] = "consumer_goods"
            yield item

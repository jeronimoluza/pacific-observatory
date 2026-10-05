"""Mexico-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MexicoScentPerfumesSpider(ShopifyBaseSpider):
    name = "mexico_scent_perfumes"
    allowed_domains = ["scentperfumes.mx"]
    base_url = "https://scentperfumes.mx"
    currency = "MXN"
    language = "es"


    def _items(self, product):
        for item in super()._items(product):
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            item["country"] = 'Mexico'
            item["sector"] = "consumer_goods"
            yield item

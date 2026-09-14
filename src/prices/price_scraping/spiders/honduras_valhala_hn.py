"""Valhala Honduras's complete public Shopify catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class HondurasValhalaHNSpider(ShopifyBaseSpider):
    name = "honduras_valhala_hn"
    allowed_domains = ["valhala.hn"]
    base_url = "https://valhala.hn"
    currency = "HNL"
    language = "es"

    def _items(self, product):
        for item in super()._items(product):
            item["country"] = "Honduras"
            item["sector"] = "consumer_goods"
            yield item

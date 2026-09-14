"""Pakistan-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class PakistanHatoylandSpider(ShopifyBaseSpider):
    name = "pakistan_hatoyland"
    allowed_domains = ["hatoyland.pk"]
    base_url = "https://hatoyland.pk"
    currency = "PKR"
    language = "en"

    def _items(self, product):
        for item in super()._items(product):
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            item["country"] = 'Pakistan'
            item["sector"] = "consumer_goods"
            yield item

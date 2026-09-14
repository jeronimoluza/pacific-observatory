"""Pakistan-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class PakistanAdnanBrothersSpider(ShopifyBaseSpider):
    name = "pakistan_adnan_brothers"
    allowed_domains = ["adnanbrothers.com"]
    base_url = "https://adnanbrothers.com"
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

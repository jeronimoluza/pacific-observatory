"""Egypt-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class Egypt3alababakSpider(ShopifyBaseSpider):
    name = "egypt_3alababak"
    allowed_domains = ["3alababak.com"]
    base_url = "https://3alababak.com"
    currency = "EGP"
    language = "ar"


    def _items(self, product):
        for item in super()._items(product):
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            item["country"] = 'Egypt'
            item["sector"] = "consumer_goods"
            yield item

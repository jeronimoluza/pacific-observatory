"""Nepal-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class NepalGreySpider(ShopifyBaseSpider):
    name = "nepal_grey"
    allowed_domains = ["grey.com.np"]
    base_url = "https://grey.com.np"
    currency = "NPR"
    language = "en"

    def _items(self, product):
        for item in super()._items(product):
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            item["country"] = 'Nepal'
            item["sector"] = "consumer_goods"
            yield item

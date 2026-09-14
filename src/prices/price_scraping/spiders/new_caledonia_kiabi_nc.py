"""New Caledonia-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class NewCaledoniaKiabiNcSpider(ShopifyBaseSpider):
    name = "new_caledonia_kiabi_nc"
    allowed_domains = ["kiabi.nc"]
    base_url = "https://kiabi.nc"
    currency = "XPF"
    language = "fr"

    def _items(self, product):
        for item in super()._items(product):
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            item["country"] = 'New Caledonia'
            item["sector"] = "consumer_goods"
            yield item

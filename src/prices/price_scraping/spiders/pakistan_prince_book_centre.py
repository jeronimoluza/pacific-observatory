"""Pakistan-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class PakistanPrinceBookCentreSpider(ShopifyBaseSpider):
    name = "pakistan_prince_book_centre"
    allowed_domains = ["princebookcentre.com"]
    base_url = "https://princebookcentre.com"
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

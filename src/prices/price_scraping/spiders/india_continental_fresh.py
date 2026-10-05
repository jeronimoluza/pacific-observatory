"""India-local public Shopify product catalogue."""
from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class IndiaContinentalFreshSpider(ShopifyBaseSpider):
    name = "india_continental_fresh"
    allowed_domains = ["continentalfresh.in"]
    base_url = "https://continentalfresh.in"
    currency = "INR"
    language = "en"


    def _items(self, product):
        for item in super()._items(product):
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            item["country"] = 'India'
            item["sector"] = "consumer_goods"
            yield item

"""iQ Jersey (Channel Islands) -- https://iqjersey.com/. Open Shopify /products.json catalog."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class IqjerseyCiSpider(ShopifyBaseSpider):
    name = "iqjersey_ci"
    allowed_domains = ["iqjersey.com"]
    base_url = "https://iqjersey.com"
    currency = "GBP"
    language = "en"

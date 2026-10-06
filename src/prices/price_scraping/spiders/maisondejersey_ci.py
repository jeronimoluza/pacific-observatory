"""maisondejersey.com (Channel Islands) -- https://www.maisondejersey.com/. Open Shopify /products.json catalog."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MaisondejerseyCiSpider(ShopifyBaseSpider):
    name = "maisondejersey_ci"
    allowed_domains = ["maisondejersey.com"]
    base_url = "https://www.maisondejersey.com"
    currency = "GBP"
    language = "en"

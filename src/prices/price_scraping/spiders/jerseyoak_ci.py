"""jerseyoak.com (Channel Islands) -- https://jerseyoak.com/. Open Shopify /products.json catalog."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class JerseyoakCiSpider(ShopifyBaseSpider):
    name = "jerseyoak_ci"
    allowed_domains = ["jerseyoak.com"]
    base_url = "https://jerseyoak.com"
    currency = "GBP"
    language = "en"

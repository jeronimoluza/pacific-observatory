"""yakwax.com (Channel Islands) -- https://yakwax.com/. Open Shopify /products.json catalog."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class YakwaxCiSpider(ShopifyBaseSpider):
    name = "yakwax_ci"
    allowed_domains = ["yakwax.com"]
    base_url = "https://yakwax.com"
    currency = "GBP"
    language = "en"

"""jerriaisclothing.com (Channel Islands) -- https://jerriaisclothing.com/. Open Shopify /products.json catalog."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class JerriaisclothingCiSpider(ShopifyBaseSpider):
    name = "jerriaisclothing_ci"
    allowed_domains = ["jerriaisclothing.com"]
    base_url = "https://jerriaisclothing.com"
    currency = "GBP"
    language = "en"

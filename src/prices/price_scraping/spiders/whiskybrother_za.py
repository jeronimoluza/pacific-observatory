"""WhiskyBrother (South Africa, Shopify) — https://whiskybrother.myshopify.com/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class WhiskybrotherZaSpider(ShopifyBaseSpider):
    name = "whiskybrother_za"
    allowed_domains = ["whiskybrother.myshopify.com"]
    base_url = "https://whiskybrother.myshopify.com"
    currency = "ZAR"
    language = "en"

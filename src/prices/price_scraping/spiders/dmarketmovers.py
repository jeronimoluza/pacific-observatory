"""D'Market Movers (Trinidad and Tobago, Shopify) — https://dmarketmovers.com/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class DmarketmoversSpider(ShopifyBaseSpider):
    name = "dmarketmovers"
    allowed_domains = ["dmarketmovers.com"]
    base_url = "https://dmarketmovers.com"
    currency = "TTD"
    language = "en"

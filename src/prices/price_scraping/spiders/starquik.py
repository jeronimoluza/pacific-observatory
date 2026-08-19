"""Star Bazaar / StarQuik (India, Tata, Shopify) — https://www.starquik.com/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class StarquikSpider(ShopifyBaseSpider):
    name = "starquik"
    allowed_domains = ["starquik.com"]
    base_url = "https://www.starquik.com"
    currency = "INR"
    language = "en"

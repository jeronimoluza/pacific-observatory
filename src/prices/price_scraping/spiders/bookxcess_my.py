"""BookXcess Malaysia books Shopify feed."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class BookxcessMySpider(ShopifyBaseSpider):
    name = "bookxcess_my"
    allowed_domains = ["bookxcess.com", "www.bookxcess.com"]
    base_url = "https://www.bookxcess.com"
    currency = "MYR"
    language = "en"

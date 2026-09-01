"""Spider for Babylove Nauru snacks collection."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class BabyloveNauruSpider(ShopifyBaseSpider):
    name = "babylove_nauru"
    allowed_domains = ["babylovenauru.com"]
    base_url = "https://babylovenauru.com"
    currency = "AUD"
    language = "en"
    PRODUCTS_PATH = "/collections/%F0%9F%8D%BD%EF%B8%8Fsnacks/products.json"

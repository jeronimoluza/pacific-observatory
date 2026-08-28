"""Yemen Box (Yemen, Shopify) — https://yemenbox.com/. Grocery collection only."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class YemenboxSpider(ShopifyBaseSpider):
    name = "yemenbox"
    allowed_domains = ["yemenbox.com"]
    base_url = "https://yemenbox.com"
    currency = "USD"
    language = "en"
    PRODUCTS_PATH = "/collections/grocery/products.json"

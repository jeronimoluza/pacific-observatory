"""Spider for Excellent Stores (Trinidad and Tobago) — Shopify department store."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MyexcellentstoresTtSpider(ShopifyBaseSpider):
    name = "myexcellentstores_tt"
    allowed_domains = ["myexcellentstores.com"]
    base_url = "https://www.myexcellentstores.com"
    currency = "TTD"
    language = "en"

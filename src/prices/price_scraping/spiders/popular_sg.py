"""POPULAR Singapore books, stationery, and electronics Shopify feed."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class PopularSgSpider(ShopifyBaseSpider):
    name = "popular_sg"
    allowed_domains = ["popularonline.com.sg", "www.popularonline.com.sg"]
    base_url = "https://popularonline.com.sg"
    currency = "SGD"
    language = "en"

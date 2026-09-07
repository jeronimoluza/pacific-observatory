"""Megafurniture Singapore furniture Shopify feed."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MegafurnitureSgSpider(ShopifyBaseSpider):
    name = "megafurniture_sg"
    allowed_domains = ["megafurniture.sg", "www.megafurniture.sg"]
    base_url = "https://megafurniture.sg"
    currency = "SGD"
    language = "en"

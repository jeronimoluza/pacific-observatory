"""Epigram Bookshop Singapore books Shopify feed."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class EpigramSgSpider(ShopifyBaseSpider):
    name = "epigram_sg"
    allowed_domains = ["epigrambookshop.sg", "www.epigrambookshop.sg"]
    base_url = "https://epigrambookshop.sg"
    currency = "SGD"
    language = "en"

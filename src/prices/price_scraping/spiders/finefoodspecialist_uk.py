"""Spider for Fine Food Specialist, a UK online specialty grocer/delicatessen
(fresh fish, meat, cheese and fresh berries/soft fruit)."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class FinefoodspecialistUkSpider(ShopifyBaseSpider):
    name = "finefoodspecialist_uk"
    allowed_domains = ["www.finefoodspecialist.co.uk"]
    base_url = "https://www.finefoodspecialist.co.uk"
    currency = "GBP"
    language = "en"

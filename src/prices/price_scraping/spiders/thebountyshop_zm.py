"""The Bounty Shop (Zambia) — https://www.thebountyshop.com. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class ThebountyshopZmSpider(WooBaseSpider):
    name = "thebountyshop_zm"
    allowed_domains = ["thebountyshop.com"]
    currency = "ZMW"
    language = "en"
    BASE_URL = "https://www.thebountyshop.com/wp-json/wc/store/v1/products"

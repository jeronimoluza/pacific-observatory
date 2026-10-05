"""theorganicshopjersey.com (Channel Islands) -- https://theorganicshopjersey.com/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class TheorganicshopjerseyCiSpider(WooBaseSpider):
    name = "theorganicshopjersey_ci"
    allowed_domains = ["theorganicshopjersey.com"]
    currency = "GBP"
    language = "en"
    BASE_URL = "https://theorganicshopjersey.com/wp-json/wc/store/v1/products"

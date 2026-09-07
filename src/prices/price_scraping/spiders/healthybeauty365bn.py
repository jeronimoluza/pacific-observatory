"""Healthy Beauty365 Brunei -- WooCommerce health and beauty storefront."""

from price_scraping.spiders._woo_base import WooBaseSpider


class HealthyBeauty365BnSpider(WooBaseSpider):
    name = "healthybeauty365bn"
    allowed_domains = ["healthybeauty365bn.com"]
    currency = "BND"
    language = "en"
    BASE_URL = "https://healthybeauty365bn.com/wp-json/wc/store/v1/products"

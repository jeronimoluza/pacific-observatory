"""Senheng Malaysia electronics and appliance WooCommerce feed."""

from price_scraping.spiders._woo_base import WooBaseSpider


class SenhengMySpider(WooBaseSpider):
    name = "senheng_my"
    allowed_domains = ["senheng.com.my", "www.senheng.com.my"]
    BASE_URL = "https://www.senheng.com.my/wp-json/wc/store/v1/products"
    currency = "MYR"
    language = "en"

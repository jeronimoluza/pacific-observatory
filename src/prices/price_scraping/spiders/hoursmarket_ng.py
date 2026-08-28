"""24 Hours Market (Nigeria, Lagos, WooCommerce) — https://24hoursmarket.com/"""

from price_scraping.spiders._woo_base import WooBaseSpider


class HoursmarketNgSpider(WooBaseSpider):
    name = "hoursmarket_ng"
    allowed_domains = ["24hoursmarket.com"]
    currency = "NGN"
    language = "en"
    BASE_URL = "https://24hoursmarket.com/wp-json/wc/store/v1/products"

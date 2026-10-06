"""
Tico BVI (British Virgin Islands) -- https://ticobvi.com/.

Tortola-based wine, spirits, beer and soft-drink merchant.
Standard WooCommerce Store API, no auth; currency_minor_unit=2, USD.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class TicobviVgSpider(WooBaseSpider):
    name = "ticobvi_vg"
    allowed_domains = ["ticobvi.com"]
    currency = "USD"
    language = "en"
    FORCE_CURRENCY = "USD"
    BASE_URL = "https://ticobvi.com/wp-json/wc/store/v1/products"

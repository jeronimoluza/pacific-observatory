"""
Klass Electronics (British Virgin Islands) -- https://klass-electronics.com/.

Road Town electronics retailer.
Standard WooCommerce Store API, no auth; currency_minor_unit=2, USD.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class KlasselectronicsVgSpider(WooBaseSpider):
    name = "klasselectronics_vg"
    allowed_domains = ["klass-electronics.com"]
    currency = "USD"
    language = "en"
    FORCE_CURRENCY = "USD"
    BASE_URL = "https://klass-electronics.com/wp-json/wc/store/v1/products"
    # chrome profiles get a 403 from this tenant; firefox133 clears it.
    IMPERSONATE_PROFILE = "firefox133"

"""
BVI Health Services Authority online pharmacy (British Virgin Islands) -- https://www.bvihsa.vg/.

Public-sector pharmacy products catalog.
Standard WooCommerce Store API, no auth; currency_minor_unit=2, USD.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class BvihsaVgSpider(WooBaseSpider):
    name = "bvihsa_vg"
    allowed_domains = ["www.bvihsa.vg"]
    currency = "USD"
    language = "en"
    FORCE_CURRENCY = "USD"
    BASE_URL = "https://www.bvihsa.vg/wp-json/wc/store/v1/products"

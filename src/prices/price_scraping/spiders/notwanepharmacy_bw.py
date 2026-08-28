"""Notwane Pharmacy (Botswana, Gaborone, WooCommerce) — https://notwanepharmacy.store/"""

from price_scraping.spiders._woo_base import WooBaseSpider


class NotwanepharmacyBwSpider(WooBaseSpider):
    name = "notwanepharmacy_bw"
    allowed_domains = ["notwanepharmacy.store"]
    currency = "BWP"
    language = "en"
    BASE_URL = "https://notwanepharmacy.store/wp-json/wc/store/v1/products"

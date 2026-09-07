"""Epicerie Eco Vrac Tahiti -- WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class EpicerieEcoVracPfSpider(WooBaseSpider):
    name = "epicerie_ecovrac_pf"
    allowed_domains = ["epicerie-ecovrac.com", "www.epicerie-ecovrac.com"]
    currency = "XPF"
    language = "fr"
    BASE_URL = "https://www.epicerie-ecovrac.com/wp-json/wc/store/v1/products"

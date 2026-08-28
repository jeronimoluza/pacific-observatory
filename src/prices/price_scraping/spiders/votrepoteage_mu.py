"""Votre Pote Age (Mauritius, fresh produce/fish, WooCommerce) — https://votrepoteage.mu/"""

from price_scraping.spiders._woo_base import WooBaseSpider


class VotrepoteageMuSpider(WooBaseSpider):
    name = "votrepoteage_mu"
    allowed_domains = ["votrepoteage.mu"]
    currency = "MUR"
    language = "fr"
    BASE_URL = "https://votrepoteage.mu/wp-json/wc/store/v1/products"

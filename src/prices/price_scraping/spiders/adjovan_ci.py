"""
Adjovan (Côte d'Ivoire) — https://www.adjovan.com/.

Standard WooCommerce Store API on the versioned route. Wide supermarket
catalog (~2,200 products) with XOF prices at currency_minor_unit=0.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class AdjovanCiSpider(WooBaseSpider):
    name = "adjovan_ci"
    allowed_domains = ["adjovan.com"]
    currency = "XOF"
    language = "fr"
    BASE_URL = "https://www.adjovan.com/wp-json/wc/store/v1/products"

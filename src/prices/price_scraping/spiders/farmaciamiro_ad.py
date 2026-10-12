"""Farmacia Miro (Andorra) -- https://www.farmaciamiro.com/.

Andorran pharmacy (Roser Miro; AD500 / +376 contact details on the storefront).
Open WooCommerce Store API at /wp-json/wc/store/v1/products, EUR; the shared
WooBaseSpider handles the minor-unit shift.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class FarmaciamiroAdSpider(WooBaseSpider):
    name = "farmaciamiro_ad"
    allowed_domains = ["farmaciamiro.com"]
    currency = "EUR"
    language = "ca"
    BASE_URL = "https://www.farmaciamiro.com/wp-json/wc/store/v1/products"

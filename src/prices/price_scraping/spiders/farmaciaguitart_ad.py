"""Farmacia Guitart (Andorra) -- https://farmaciaguitart.com/.

Andorran retailer (AD500 / +376 contact details on the site). Open WooCommerce
Store API at /wp-json/wc/store/v1/products, EUR; the shared WooBaseSpider
handles the minor-unit shift.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class FarmaciaguitartAdSpider(WooBaseSpider):
    name = "farmaciaguitart_ad"
    allowed_domains = ["farmaciaguitart.com"]
    currency = "EUR"
    language = "ca"
    BASE_URL = "https://farmaciaguitart.com/wp-json/wc/store/v1/products"

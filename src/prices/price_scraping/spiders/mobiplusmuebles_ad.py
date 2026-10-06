"""Mobiplus Muebles (Andorra) -- https://mobiplusmuebles.com/.

Andorran retailer (AD500 / +376 contact details on the site). Open WooCommerce
Store API at /wp-json/wc/store/v1/products, EUR; the shared WooBaseSpider
handles the minor-unit shift.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class MobiplusmueblesAdSpider(WooBaseSpider):
    name = "mobiplusmuebles_ad"
    allowed_domains = ["mobiplusmuebles.com"]
    currency = "EUR"
    language = "es"
    BASE_URL = "https://mobiplusmuebles.com/wp-json/wc/store/v1/products"

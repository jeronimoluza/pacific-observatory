"""
The Wine Boutique (Eswatini) - thewineboutique.net.

Standard WooCommerce Store API. SZL prices at currency_minor_unit=2.
Catalog is mostly wine/spirits/sparkling wine/gift hampers, with a
handful of unrelated merchandise (e.g. a bucket hat) mixed in -- not
purely one COICOP class, so coicop_codes is left unset for the
classifier. ~187 products confirmed by walking the store API to an
empty page.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class ThewineboutiqueSzSpider(WooBaseSpider):
    name = "thewineboutique_sz"
    allowed_domains = ["thewineboutique.net"]
    currency = "SZL"
    language = "en"
    BASE_URL = "https://thewineboutique.net/wp-json/wc/store/v1/products"

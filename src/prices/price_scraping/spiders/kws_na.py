"""
Klein Windhoek Schlachterei -- https://kwsnamibia.shop/ (butcher, fresh meat).

Standard WooCommerce Store API at /wp-json/wc/store/v1/products. NAD
prices at currency_minor_unit=2 (e.g. raw "19995" -> N$199.95), confirmed
against the site's own price_html on the same row.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class KwsNaSpider(WooBaseSpider):
    name = "kws_na"
    allowed_domains = ["kwsnamibia.shop"]
    currency = "NAD"
    language = "en"
    BASE_URL = "https://kwsnamibia.shop/wp-json/wc/store/v1/products"

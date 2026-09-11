"""
Waltons -- https://www.waltons.com.na/ (office, stationery and electronics
retail chain, Namibian storefront of the South African Waltons group).

Standard WooCommerce Store API at /wp-json/wc/store/v1/products. NAD
prices at currency_minor_unit=2 (e.g. raw "302116100021"-style SKU aside,
prices such as raw "1999" -> N$19.99), confirmed against the site's own
price_html on the same row.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class WaltonsNaSpider(WooBaseSpider):
    name = "waltons_na"
    allowed_domains = ["waltons.com.na", "www.waltons.com.na"]
    currency = "NAD"
    language = "en"
    BASE_URL = "https://waltons.com.na/wp-json/wc/store/v1/products"

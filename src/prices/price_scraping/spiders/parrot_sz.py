"""
Parrot Products Eswatini - parrot.co.sz.

Standard WooCommerce Store API. SZL prices at currency_minor_unit=2.
Catalog spans office/education electronics and stationery -- projector
screens, whiteboards, flipcharts, laser pointers, planners -- ~233
products confirmed by walking the store API to an empty page.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class ParrotSzSpider(WooBaseSpider):
    name = "parrot_sz"
    allowed_domains = ["parrot.co.sz"]
    currency = "SZL"
    language = "en"
    BASE_URL = "https://parrot.co.sz/wp-json/wc/store/v1/products"

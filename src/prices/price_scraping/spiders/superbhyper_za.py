"""
SuperbHyper (South Africa, Durban / North Coast) — https://superbhyper.co.za/.

Standard WooCommerce Store API. Wide catalog, ZAR minor-unit prices.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class SuperbhyperZaSpider(WooBaseSpider):
    name = "superbhyper_za"
    allowed_domains = ["superbhyper.co.za"]
    currency = "ZAR"
    language = "en"
    BASE_URL = "https://superbhyper.co.za/wp-json/wc/store/v1/products"

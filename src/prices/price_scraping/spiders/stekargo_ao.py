"""
Stekargo (Angola) — https://stekargo.com/.

Standard WooCommerce Store API on the versioned route, no auth. Cross-division
Angolan online store (~3,350 products): books/stationery dominate, but there is
a real COICOP-01/02 tail — Café e Chá (140), Café (107), Chá (34), Bebidas (24),
Chocolates (21), Alimentação Saudável (16) — which is why the whole catalogue is
walked and left to the classifier. AOA at currency_minor_unit=0.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class StekargoAoSpider(WooBaseSpider):
    name = "stekargo_ao"
    allowed_domains = ["stekargo.com", "www.stekargo.com"]
    currency = "AOA"
    language = "pt"
    BASE_URL = "https://stekargo.com/wp-json/wc/store/v1/products"

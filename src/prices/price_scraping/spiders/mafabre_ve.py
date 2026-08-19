"""
Mafabre (Venezuela) — https://mafabre.com/.

Caracas food distributor turned online grocery; prices in USD (dollarized
retail is standard in VE), not the country's official VES.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class MafabreVeSpider(WooBaseSpider):
    name = "mafabre_ve"
    allowed_domains = ["mafabre.com"]
    currency = "USD"
    language = "es"
    BASE_URL = "https://mafabre.com/wp-json/wc/store/v1/products"

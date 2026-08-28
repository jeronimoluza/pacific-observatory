"""
Supermercados Pao Trolado (Venezuela) — https://supermercados-paotrolado.com/.

Mixed household/grocery online store; prices in USD (dollarized retail is
standard in VE), not the country's official VES.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class PaotroladoVeSpider(WooBaseSpider):
    name = "paotrolado_ve"
    allowed_domains = ["supermercados-paotrolado.com"]
    currency = "USD"
    language = "es"
    BASE_URL = "https://supermercados-paotrolado.com/wp-json/wc/store/v1/products"

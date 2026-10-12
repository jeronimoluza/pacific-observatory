"""Eternal Andorra (Andorra) -- https://eternalandorra.pro/.

Andorran official Joma sportswear distributor and club merchandise shop (Inter
Escaldes; AD500 address). Open WooCommerce Store API at
/wp-json/wc/store/v1/products, EUR; the shared WooBaseSpider handles the
minor-unit shift. Small catalogue (about 30 SKUs).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class EternalandorraAdSpider(WooBaseSpider):
    name = "eternalandorra_ad"
    allowed_domains = ["eternalandorra.pro"]
    currency = "EUR"
    language = "ca"
    BASE_URL = "https://eternalandorra.pro/wp-json/wc/store/v1/products"

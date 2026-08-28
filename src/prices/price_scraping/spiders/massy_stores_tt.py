"""
Massy Stores Trinidad -- https://www.shopmassystorestt.com/.

Separate WooCommerce tenant from massy_stores_bb (Barbados) -- distinct
catalog/currency per territory. Default /wp-json/wc/store/v1/products path
works directly on this install (no ?rest_route= workaround needed).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class MassyStoresTtSpider(WooBaseSpider):
    name = "massy_stores_tt"
    allowed_domains = ["shopmassystorestt.com", "www.shopmassystorestt.com"]
    currency = "TTD"
    language = "en"
    BASE_URL = "https://www.shopmassystorestt.com/wp-json/wc/store/v1/products"

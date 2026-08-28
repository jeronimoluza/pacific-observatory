"""
VIP Supermercado (Mozambique) — https://vipspar.com/.

Multi-vendor (Dokan) WooCommerce install; the versioned wc/store/v1/products
route 404s here, but the older non-versioned wc/store/products route works.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class VipsparMzSpider(WooBaseSpider):
    name = "vipspar_mz"
    allowed_domains = ["vipspar.com"]
    currency = "MZN"
    language = "pt"
    BASE_URL = "https://vipspar.com/wp-json/wc/store/products"

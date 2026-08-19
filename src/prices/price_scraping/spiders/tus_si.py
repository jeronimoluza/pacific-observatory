"""
Tus (Slovenia) — https://www.tus.si/.

WooCommerce storefront; the versioned wc/store/v1/products route 404s
here, but the older non-versioned wc/store/products route works (same
gotcha as vipspar_mz). Re-verified live 2026-08-06: GET
/wp-json/wc/store/products?per_page=5 -> 200, real product 'Ledena kava,
1 l' EUR 1.34 (sale, regular 2.69), minor_unit=2.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class TusSiSpider(WooBaseSpider):
    name = "tus_si"
    allowed_domains = ["tus.si"]
    currency = "EUR"
    language = "sl"
    BASE_URL = "https://www.tus.si/wp-json/wc/store/products"

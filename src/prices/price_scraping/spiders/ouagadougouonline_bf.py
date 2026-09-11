"""
Ouagadougou Online (Burkina Faso) -- https://www.ouagadougou.online/.

General WooCommerce dropship marketplace (~90 categories, electronics/
hardware/pharma dominate); scoped here to category=62 ("Alimentation &
Boissons", 547 products) rather than the whole catalog.

MINOR-UNIT TRAP: the store reports currency_minor_unit=2 for XOF, but XOF
carries no subdivisions -- the tenant's WooCommerce currency config is
simply wrong. The shared _woo_base divides by 100 unconditionally, which
would silently ship every row ~100x too low (raw 700 -> displayed
"CFA7.00" for a box of 100 Lipton tea bags -- confirmed against the
vendor's own rendered PDP, so this is the site's own bug, not our
parsing). PRICE_MULTIPLIER=100 gated on PRICE_MULTIPLIER_CURRENCY="XOF"
cancels that division. Verified against the Store API and rendered PDP
markup 2026-09-11 (same pattern as ecomguinee_gn.py's GNF fix).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class OuagadougouonlineBfSpider(WooBaseSpider):
    name = "ouagadougouonline_bf"
    allowed_domains = ["ouagadougou.online"]
    currency = "XOF"
    language = "fr"
    BASE_URL = "https://www.ouagadougou.online/wp-json/wc/store/v1/products"
    CATEGORY_ID = 62
    PRICE_MULTIPLIER = 100
    PRICE_MULTIPLIER_CURRENCY = "XOF"

"""
Ecom Guinée (Guinea) -- https://www.ecomguinee.com/.

Standard WooCommerce Store API on the versioned route. Small catalog
(~52 products, electronics/gadgets: GPS trackers, security cameras,
solar inverters).

MINOR-UNIT TRAP: the store reports currency_minor_unit=3 for GNF, but the
raw `prices.price` integer already equals the displayed amount (e.g. raw
600000 == storefront "600.000 Fr" == 600,000 GNF) -- GNF has no
subdivisions, so the tenant's minor_unit is simply misconfigured. The
shared _woo_base divides by 10**minor_unit unconditionally, which would
silently under-price every row 1000x. PRICE_MULTIPLIER=1000 (gated on
PRICE_MULTIPLIER_CURRENCY="GNF") undoes that division. Verified against
two live product pages 2026-08-31.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class EcomguineeGnSpider(WooBaseSpider):
    name = "ecomguinee_gn"
    allowed_domains = ["ecomguinee.com"]
    currency = "GNF"
    language = "fr"
    BASE_URL = "https://www.ecomguinee.com/wp-json/wc/store/v1/products"
    PRICE_MULTIPLIER = 1000
    PRICE_MULTIPLIER_CURRENCY = "GNF"

"""
Doctornice (doctornice.ir) — Iranian skincare/cosmetics WooCommerce store.

Verified live 2026-08-18: /wp-json/wc/store/v1/products (WooCommerce Store
API) is open, no auth, paginates cleanly. prices.currency_code returns
"IRT" (Toman, non-ISO) with currency_minor_unit 0 -- 1 Toman = 10 Rial, so
FORCE_CURRENCY="IRR" + PRICE_MULTIPLIER=10 report the scraped Toman value
as Rial, matching the torob_ir/sheypoor_ir convention already used for
other Iranian sources in this repo (IRR is the only ISO 4217 code for
Iran; Toman has none).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class DoctorniceIrSpider(WooBaseSpider):
    name = "doctornice_ir"
    allowed_domains = ["doctornice.ir"]
    currency = "IRR"
    language = "fa"
    BASE_URL = "https://doctornice.ir/wp-json/wc/store/v1/products"
    FORCE_CURRENCY = "IRR"
    PRICE_MULTIPLIER = 10
    PRICE_MULTIPLIER_CURRENCY = "IRT"

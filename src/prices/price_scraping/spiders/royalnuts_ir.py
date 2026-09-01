"""
Royal Nuts (royalnuts.ir) — Iranian specialty-food (nuts/dried fruit/spices/
sweets) WooCommerce store.

Verified live 2026-09-01: /wp-json/wc/store/v1/products (WooCommerce Store
API) is open, no auth, paginates cleanly (X-WP-Total: 2228 at per_page=1).
Category list confirms a genuine specialty-food catalog: nuts (آجیل),
pistachios (پسته), dried fruit (خشکبار), dates (خرما), spices/herbs (ادویه
و چاشنی), tea (چای), chocolate gift boxes, cookies (بیسکویت), sauces.
prices.currency_code returns "IRT" (Toman, non-ISO) with currency_minor_unit
0 -- 1 Toman = 10 Rial, so FORCE_CURRENCY="IRR" + PRICE_MULTIPLIER=10 report
the scraped Toman value as Rial, matching the adibmarket_ir/hastmarket_ir
convention already used for other Iranian sources in this repo (IRR is the
only ISO 4217 code for Iran; Toman has none).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class RoyalnutsIrSpider(WooBaseSpider):
    name = "royalnuts_ir"
    allowed_domains = ["royalnuts.ir"]
    currency = "IRR"
    language = "fa"
    BASE_URL = "https://royalnuts.ir/wp-json/wc/store/v1/products"
    FORCE_CURRENCY = "IRR"
    PRICE_MULTIPLIER = 10
    PRICE_MULTIPLIER_CURRENCY = "IRT"

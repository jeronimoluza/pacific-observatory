"""
Iranian Style (iranian-style.com) -- Iranian apparel WooCommerce store.

Verified live 2026-09-28: /wp-json/wc/store/v1/products (WooCommerce Store
API) is open, no auth, paginates cleanly. prices.currency_code returns
"IRT" (Toman, non-ISO) with currency_minor_unit 0 -- 1 Toman = 10 Rial, so
FORCE_CURRENCY="IRR" + PRICE_MULTIPLIER=10 report the scraped Toman value
as Rial, matching the adibmarket_ir/torob_ir/sheypoor_ir convention
already used for other Iranian sources in this repo. Sample product:
cotton trench coat (product slug cotton-trench-coat-c51014), price
1,220,000 IRT -> 12,200,000 IRR. Sampled product categories are women's
outerwear/winter clothing -- women's apparel-led catalog, fills the
clothing COICOP 03 gap; existing Iran manifests are cosmetics/pharmacy/
food-led. Page family: API (spider reads the Store API directly, never
fetches a rendered page).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class IranianStyleIrSpider(WooBaseSpider):
    name = "iranian_style_ir"
    allowed_domains = ["iranian-style.com"]
    currency = "IRR"
    language = "fa"
    BASE_URL = "https://iranian-style.com/wp-json/wc/store/v1/products"
    FORCE_CURRENCY = "IRR"
    PRICE_MULTIPLIER = 10
    PRICE_MULTIPLIER_CURRENCY = "IRT"

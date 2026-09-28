"""
Dominokala (dominokala.ir/.com) -- Iranian home-appliance WooCommerce store.

Verified live 2026-09-28: /wp-json/wc/store/v1/products (WooCommerce Store
API) is open, no auth, paginates cleanly (page1/page2 return disjoint ids).
prices.currency_code returns "IRT" (Toman, non-ISO) with
currency_minor_unit 0 -- 1 Toman = 10 Rial, so FORCE_CURRENCY="IRR" +
PRICE_MULTIPLIER=10 report the scraped Toman value as Rial, matching the
adibmarket_ir/torob_ir/sheypoor_ir convention already used for other
Iranian sources in this repo. Sample product: "جاروبرقی آاگ مدل
AEG VX9-2-OKO" (AEG VX9-2-OKO vacuum cleaner), price 71,597,000 IRT ->
715,970,000 IRR. Catalog is home/kitchen appliances (vacuum cleaners,
printers seen in sibling stores) -- fills the household-equipment
(COICOP 05) gap; existing Iran manifests are cosmetics/pharmacy/food-led.
Page family: API (spider reads the Store API directly, never fetches a
rendered page).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class DominokalaIrSpider(WooBaseSpider):
    name = "dominokala_ir"
    allowed_domains = ["dominokala.com"]
    currency = "IRR"
    language = "fa"
    BASE_URL = "https://dominokala.com/wp-json/wc/store/v1/products"
    FORCE_CURRENCY = "IRR"
    PRICE_MULTIPLIER = 10
    PRICE_MULTIPLIER_CURRENCY = "IRT"

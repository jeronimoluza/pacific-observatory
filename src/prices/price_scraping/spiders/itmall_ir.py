"""
ITMall (itmall.ir) -- Iranian consumer-electronics WooCommerce store.

Verified live 2026-09-28: /wp-json/wc/store/v1/products (WooCommerce Store
API) is open, no auth, paginates cleanly (page1/page2 return disjoint ids).
prices.currency_code returns "IRT" (Toman, non-ISO) with
currency_minor_unit 0 -- 1 Toman = 10 Rial, so FORCE_CURRENCY="IRR" +
PRICE_MULTIPLIER=10 report the scraped Toman value as Rial, matching the
adibmarket_ir/torob_ir/sheypoor_ir convention already used for other
Iranian sources in this repo. Sample products: Xiaomi power banks
(PB2030MI 20000mAh @6,000,000 IRT), ASUS TUF Gaming FA506 laptops
(240,999,000-381,499,000 IRT), Samsung Galaxy A37 5G
(102,000,000 IRT) -- genuine consumer electronics, real varied prices,
not a B2B quote-on-request catalog (unlike javan-electronic.ir, dead-ended
in the same pass: every sampled item price=0). Fills the electronics
(COICOP 05/09) gap; existing Iran manifests are cosmetics/pharmacy/
food-led. Page family: API (spider reads the Store API directly, never
fetches a rendered page).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class ItmallIrSpider(WooBaseSpider):
    name = "itmall_ir"
    allowed_domains = ["itmall.ir"]
    currency = "IRR"
    language = "fa"
    BASE_URL = "https://itmall.ir/wp-json/wc/store/v1/products"
    FORCE_CURRENCY = "IRR"
    PRICE_MULTIPLIER = 10
    PRICE_MULTIPLIER_CURRENCY = "IRT"

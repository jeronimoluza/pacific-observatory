"""
Mahak Cosmetic (Iran) — https://mahak-cosmetic.ir/.

Cosmetics/personal-care storefront ("فروشگاه آرایشی بهداشتی ماهک کازمتیک").
WooCommerce storefront; the versioned wc/store/v1/products route confirmed
live 2026-08-18, e.g. an original Dior Sauvage 100ml eau de cologne
price=1920000 currency_code=IRT.

Toman/Rial: the Store API's currency_code is the non-ISO "IRT" (Toman) on
every sampled product here, and the site's own product-page meta tags
confirm the x10 relationship for this exact product (Store API 1920000 IRT
<-> meta tag 19200000 IRR). ISO 4217 has no Toman code — same convention as
sheypoor_ir/torob_ir — so `_item` multiplies by 10 and reports IRR.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class MahakCosmeticIrSpider(WooBaseSpider):
    name = "mahak_cosmetic_ir"
    allowed_domains = ["mahak-cosmetic.ir"]
    currency = "IRR"
    language = "fa"
    BASE_URL = "https://mahak-cosmetic.ir/wp-json/wc/store/v1/products"

    PRICE_MULTIPLIER = 10
    PRICE_MULTIPLIER_CURRENCY = "IRT"

"""
ELL Beauty (Iran) — https://ellbeauty.ir/.

Cosmetics/beauty storefront ("Cosmetics + Beauty Products - ELL BEAUTY").
WooCommerce storefront; the versioned wc/store/v1/products route confirmed
live 2026-08-18, e.g. 'Clinique Take The Day Off Makeup Remover For Lids,
Lashes & Lips 125ml' price=1296000 currency_code=IRT.

Toman/Rial: the Store API's currency_code is the non-ISO "IRT" (Toman) on
every sampled product here — same storefront family and convention as the
sibling Iranian cosmetics stores onboarded alongside this one
(arayeshishahin_ir, dubaik_ir). ISO 4217 has no Toman code — same
convention as sheypoor_ir/torob_ir — so `_item` multiplies by 10 and
reports IRR.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class EllbeautyIrSpider(WooBaseSpider):
    name = "ellbeauty_ir"
    allowed_domains = ["ellbeauty.ir"]
    currency = "IRR"
    language = "fa"
    BASE_URL = "https://ellbeauty.ir/wp-json/wc/store/v1/products"

    PRICE_MULTIPLIER = 10
    PRICE_MULTIPLIER_CURRENCY = "IRT"

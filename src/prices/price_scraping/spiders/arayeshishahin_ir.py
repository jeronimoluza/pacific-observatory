"""
Arayeshi Shahin (Iran) — https://arayeshishahin.ir/.

Cosmetics/personal-care storefront ("آرایشی شاهین - فروشگاه لوازم آرایشی و
بهداشتی"). WooCommerce storefront; the versioned wc/store/v1/products route
confirmed live 2026-08-18, e.g. 'DEMI EYEBROW LIFT GEL 10G' price=548000
currency_code=IRT.

Toman/Rial: the Store API's currency_code is the non-ISO "IRT" (Toman) on
every sampled product here, and the site's own product-page meta tags
confirm the value is Toman-denominated (meta tag also states 548000 IRT for
the same product — the site's markup itself names Toman, unlike the sibling
mahak-cosmetic.ir/khayamdaru.ir which mislabel the same Toman-scale value as
"IRR" in their meta tags). ISO 4217 has no Toman code — same convention as
sheypoor_ir/torob_ir — so `_item` multiplies by 10 and reports IRR.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class ArayeshishahinIrSpider(WooBaseSpider):
    name = "arayeshishahin_ir"
    allowed_domains = ["arayeshishahin.ir"]
    currency = "IRR"
    language = "fa"
    BASE_URL = "https://arayeshishahin.ir/wp-json/wc/store/v1/products"

    PRICE_MULTIPLIER = 10
    PRICE_MULTIPLIER_CURRENCY = "IRT"

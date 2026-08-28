"""
Dubaik (Iran) — https://dubaik.ir/.

Cosmetics/skincare storefront selling imported (Dubai-sourced) products
("خرید محصولات آرایشی و بهداشتی اصل | فروشگاه دبیک"). WooCommerce
storefront; the versioned wc/store/v1/products route confirmed live
2026-08-18, e.g. a Namboozin NAD+ Retinal eye cream price=2217000
currency_code=IRT.

Toman/Rial: the Store API's currency_code is the non-ISO "IRT" (Toman) on
every sampled product here, and the site's own product-page meta tags
confirm the value is Toman-denominated (meta tag also states 2217000 IRT
for the same product). ISO 4217 has no Toman code — same convention as
sheypoor_ir/torob_ir — so `_item` multiplies by 10 and reports IRR.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class DubaikIrSpider(WooBaseSpider):
    name = "dubaik_ir"
    allowed_domains = ["dubaik.ir"]
    currency = "IRR"
    language = "fa"
    BASE_URL = "https://dubaik.ir/wp-json/wc/store/v1/products"

    PRICE_MULTIPLIER = 10
    PRICE_MULTIPLIER_CURRENCY = "IRT"

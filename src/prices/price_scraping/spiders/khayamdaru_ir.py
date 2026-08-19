"""
Khayam Darou (Iran) — https://khayamdaru.ir/.

Online pharmacy ("داروخانه آنلاین خیام دارو") selling pharmaceuticals and
bodybuilding/nutrition supplements, a subsidiary of Dr. Shourabi Pharmacy.
WooCommerce storefront; the versioned wc/store/v1/products route confirmed
live 2026-08-18, e.g. 'Universal Animal Whey 2300g' price=19800000
currency_code=IRT.

Toman/Rial: the Store API's currency_code is the non-ISO "IRT" (Toman) on
every sampled product here, and the site's own product-page meta tags
confirm the x10 relationship (Store API 1920000 IRT <-> meta tag 19200000
IRR for the same product on the sibling site mahak-cosmetic.ir, same
storefront template). ISO 4217 has no Toman code — same convention as
sheypoor_ir/torob_ir — so `_item` multiplies by 10 and reports IRR.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class KhayamdaruIrSpider(WooBaseSpider):
    name = "khayamdaru_ir"
    allowed_domains = ["khayamdaru.ir"]
    currency = "IRR"
    language = "fa"
    BASE_URL = "https://khayamdaru.ir/wp-json/wc/store/v1/products"

    PRICE_MULTIPLIER = 10
    PRICE_MULTIPLIER_CURRENCY = "IRT"

"""
Hami cosmetics/personal-care store (Iran) -- https://hami.ir/.

فروشگاه حامی -- WooCommerce Store API is open and unauthenticated. The
API's currency_code is "IRT" (Toman), which has no ISO 4217 code -- same
convention already used by torob_ir/sheypoor_ir: multiply by 10 and
report as IRR. Confirmed live 2026-08-18 that the site's own PDP
JSON-LD does exactly this conversion: API price 3,280,000 Toman for
"میست آبرسان کپسولی PDRN و هیالورونیک اسید آنوا" == JSON-LD 32,800,000
IRR.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class HamiIrSpider(WooBaseSpider):
    name = "hami_ir"
    allowed_domains = ["hami.ir"]
    currency = "IRR"
    language = "fa"
    BASE_URL = "https://hami.ir/wp-json/wc/store/v1/products"

    PRICE_MULTIPLIER = 10
    PRICE_MULTIPLIER_CURRENCY = "IRT"

    def _item(self, p: dict):
        item = super()._item(p)
        if item is None or float(item["price"]) <= 0:
            return None
        return item

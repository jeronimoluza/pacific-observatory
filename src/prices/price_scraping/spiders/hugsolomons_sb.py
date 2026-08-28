"""HUG Solomons (Solomon Islands) -- https://www.hugsolomons.com/. Wellness/
general-goods WooCommerce storefront (food, body care, over-the-counter
medicine, clothing). Store API is open (verified 2026-08-11, HTTP 200,
x-wp-total: 134). Also runs an affiliate/MLM membership program whose
non-physical "products" (rank levels, cash-deposit, digital products,
services) are not real price observations and are filtered out at parse
time -- they carry no unit/quantity and would pollute the corpus."""

from price_scraping.spiders._woo_base import WooBaseSpider

_EXCLUDED_CATEGORIES = {"Cash Deposit", "Rank Level", "Digital Products", "Services"}


class HugsolomonsSbSpider(WooBaseSpider):
    name = "hugsolomons_sb"
    allowed_domains = ["hugsolomons.com"]
    currency = "SBD"
    language = "en"
    BASE_URL = "https://www.hugsolomons.com/wp-json/wc/store/v1/products"

    def _item(self, p: dict):
        cats = {
            c.get("name") for c in (p.get("categories") or []) if isinstance(c, dict)
        }
        if cats & _EXCLUDED_CATEGORIES:
            return None
        return super()._item(p)

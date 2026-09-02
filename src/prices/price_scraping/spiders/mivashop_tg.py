"""
Mivashop (Togo) — https://mivashop.com/.

Online grocery/general-goods storefront for Lome. Category id 16
("ALIMENTATION GENERALE", 924 products, top-level) is the dedicated food
category; the unfiltered catalog also carries a large restaurant-menu
vertical ("RESTAURANTS & CUISINE") which is out of scope for a retail
price series, so we scope to category=16.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class MivashopTgSpider(WooBaseSpider):
    name = "mivashop_tg"
    allowed_domains = ["mivashop.com"]
    currency = "XOF"
    language = "fr"
    BASE_URL = "https://mivashop.com/wp-json/wc/store/v1/products"
    CATEGORY_ID = 16

    def _item(self, p: dict):
        # A few listings carry a literal 0 price (display-only rows).
        # A zero price is never a usable observation, so drop them.
        row = super()._item(p)
        if row is None or float(row["price"] or 0) == 0:
            return None
        return row

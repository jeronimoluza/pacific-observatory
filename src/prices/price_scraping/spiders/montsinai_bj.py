"""
Supermarché Mont Sinaï (Benin) — https://www.supermarchemontsinai.com/.

Standard WooCommerce Store API on the versioned route. Wide supermarket
catalog (~485 products across cosmetics, pet food, beverages, groceries)
with XOF prices at currency_minor_unit=0. Site copy explicitly promises
delivery "partout à Cotonou" (Benin).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class MontsinaiBjSpider(WooBaseSpider):
    name = "montsinai_bj"
    allowed_domains = ["supermarchemontsinai.com"]
    currency = "XOF"
    language = "fr"
    BASE_URL = "https://www.supermarchemontsinai.com/wp-json/wc/store/v1/products"

    def _item(self, p: dict):
        # A handful of listings carry a literal 0 price (display-only /
        # out-of-stock rows). A zero price is never a usable observation,
        # so drop them rather than ship them.
        row = super()._item(p)
        if row is None or float(row["price"] or 0) == 0:
            return None
        return row

"""
Parapharmacie Djeddi (Algeria) — https://djeddi-pharmacie-dz.com/.

Online parapharmacy. Standard WooCommerce Store API. Re-verified live
2026-08-31: GET /wp-json/wc/store/v1/products?per_page=10 -> 200 JSON,
currency_code DZD, currency_minor_unit=0. X-WP-Total reports 2,988
products / 299 pages.

Trap: the default (newest-first) ordering front-loads recently-added
listings that carry a placeholder price of "0" and is_purchasable=false
(not yet priced / not for sale) -- 44% of the first 200 rows sampled were
zero-price, vs 0% by page 50+. Overriding `_item` to skip
is_purchasable=false rows before they reach the base class's price
handling avoids shipping ~200 client's placeholder rows per --max-items
run and keeps distinct-priced-product coverage representative of the
whole catalog rather than just its newest slice.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class DjeddiPharmacieDzSpider(WooBaseSpider):
    name = "djeddi_pharmacie_dz"
    allowed_domains = ["djeddi-pharmacie-dz.com"]
    currency = "DZD"
    language = "fr"
    BASE_URL = "https://djeddi-pharmacie-dz.com/wp-json/wc/store/v1/products"

    def _item(self, p: dict):
        if not p.get("is_purchasable", True):
            return None
        return super()._item(p)

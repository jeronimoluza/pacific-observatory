"""
Orchidea Para Pharmacie by Bensahli (Algeria) — https://orchidea-dz.com/.

Online parapharmacy. Standard WooCommerce Store API. Re-verified live
2026-08-31: GET /wp-json/wc/store/v1/products?per_page=10 -> 200 JSON,
currency_code DZD, currency_minor_unit=2. X-WP-Total reports 1,301
products / 131 pages. Zero-price placeholder listings (is_purchasable=false) are skipped in
_item; every zero-price row sampled carried that flag.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class OrchideaDzSpider(WooBaseSpider):
    name = "orchidea_dz"
    allowed_domains = ["orchidea-dz.com"]
    currency = "DZD"
    language = "fr"
    BASE_URL = "https://orchidea-dz.com/wp-json/wc/store/v1/products"

    def _item(self, p: dict):
        # Placeholder listings carry price "0" with is_purchasable=false;
        # every zero-price row sampled was one. Drop before the base's
        # price handling so no zero-price observation ever ships.
        if not p.get("is_purchasable", True):
            return None
        return super()._item(p)

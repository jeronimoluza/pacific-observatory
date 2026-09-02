"""RizqMarket (Sudan) -- https://rizqmarket.com/, a WooCommerce marketplace.

Standard WooCommerce Store API at /wp-json/wc/store/v1/products, plain
curl_cffi GET (no bot wall). Wide catalog (800+ products confirmed through
page 8 of per_page=100, real cursor pagination -- each page returned a
disjoint id set). Mixed marketplace: perfumes, women's fashion, appliances
and electronics, but also a real food-and-beverage vertical (food, fresh
produce, juices categories were ~35-40% of a 100-product sample) -- WA-
sourced product photos ("IMG-*-WA*.jpg") suggest small local sellers
uploading their own stock, not a single curated grocer, but pricing is
still real SDG retail pricing.

Trap (same as djeddi_pharmacie_dz.py): a meaningful slice of listings
(29% of a 200-row sample) carry a placeholder price of "0" with
is_purchasable=false -- sellers who listed a product photo/name but never
set a price. Overriding `_item` to skip is_purchasable=false rows before
they reach the base class avoids shipping placeholder zero-price rows.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class RizqmarketSdSpider(WooBaseSpider):
    name = "rizqmarket_sd"
    allowed_domains = ["rizqmarket.com"]
    currency = "SDG"
    language = "ar"
    BASE_URL = "https://rizqmarket.com/wp-json/wc/store/v1/products"

    def _item(self, p: dict):
        if not p.get("is_purchasable", True):
            return None
        return super()._item(p)

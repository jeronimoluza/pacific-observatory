"""
Situcka (Equatorial Guinea) — https://situcka.com/.

WooCommerce Store API storefront (open, unauthenticated
/wp-json/wc/store/v1/products), confirmed live 2026-09-01. Situcka is a
general multi-vendor marketplace for Malabo/Bata (restaurants, cosmetics,
hardware, art, weight-loss products, and a "Supermercados" umbrella
aggregating several distinct physical supermarket chains that otherwise
have no online catalogue of their own — e.g. Martinez Hermanos, EG's
largest chain, whose own corporate site (martinezhermanos.com) is a
brochure with zero products).

This is Equatorial Guinea's FIRST price source of any kind (country had 0
manifests before this pass). Scoped to CATEGORY_ID=24 ("Supermercados"),
the parent category aggregating 6 distinct supermarket vendors (Martinez
Hermanos id=26/4123 products, Guinaco id=181/2556, Ecua Market id=774/176,
EGTC id=487/16, Mangarams id=597/14, Pegasos id=642/16 — 6931 products
total per the store API's own category counts) — this excludes the
marketplace's non-food verticals (restaurantes id=16/1652, cosmeticos
id=465/842, ferreteria id=267/442, arte id=242/73, papeleria id=248/93,
etc.) entirely. Tagged channel=marketplace (not supermarket) because the
scoped category still aggregates multiple distinct operators under one
platform, per the WooBaseSpider/assivito_tg convention of scoping a
general marketplace to its food-relevant subtree — see that spider's
docstring for the precedent. Unlike assivito_tg (food is a minor category
among artisans/real-estate/vehicles), Situcka's own top-level category
counts show restaurantes+supermercados+mercado+finca-de-sampaka = 8636 of
10391 total products (83%) — this marketplace is itself food-and-beverage
led; CATEGORY_ID=24 narrows it further to literal supermarket vendors only.

Currency: XAF, currency_minor_unit=0 (integer, no decimals) confirmed via
a live store-API product payload — matches XAF's known integer-currency
trap (see skill rule 11).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class SituckaGqSpider(WooBaseSpider):
    name = "situcka_gq"
    allowed_domains = ["situcka.com"]
    currency = "XAF"
    language = "es"
    BASE_URL = "https://situcka.com/wp-json/wc/store/v1/products"
    CATEGORY_ID = 24

    def _item(self, p: dict):
        # Three rows (2 wines, 1 mug set) come back at price 0 - the
        # platform's out-of-stock / price-on-request placeholder. A zero is
        # not a price observation, so drop rather than ship it. Overridden
        # here rather than in _woo_base because that base is shared with
        # dozens of live spiders in other countries. Note the base method is
        # `_item` (singular, one dict), not `_items`.
        item = super()._item(p)
        if item is None:
            return None
        try:
            if float(item["price"]) <= 0:
                return None
        except (TypeError, ValueError, KeyError):
            pass
        return item

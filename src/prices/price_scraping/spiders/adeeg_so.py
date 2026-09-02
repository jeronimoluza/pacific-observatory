"""
Adeeg.com (Somalia) — https://adeeg.com/.

Hayat Market's official e-commerce platform (Mogadishu). Vanilla Shopify
storefront — /products.json?limit=250&page=N confirmed live 2026-09-01
(curl_cffi impersonate=chrome124), ~3,777 products across 16 pages.
Shopify.currency on the storefront reports "active":"USD" (confirmed in
the page's inline Shopify.currency JS object) — priced in USD, not the
countries.yaml default SOS.

Big-box catalogue: groceries (baby food/milk, dairy & cheese, spices,
canned foods, bakery, butchery, breakfast cereals, chips/snacks) cross-
sold with general merchandise (electronics, baby gear, books, cameras,
belts/caps) — `channel: hypermarket` per GLOSSARY.md ("big-box genuinely
cross-selling food and general merchandise").

hayatmarket.com (the brand's own domain) was checked and is NOT a
duplicate storefront — it is a WordPress/Newfold marketing site with no
WooCommerce REST/Store API route registered and a 404 on /shop/; adeeg.com
is the operator's only real e-commerce surface. Do not onboard both.

Uses the shared _shopify_base.ShopifyBaseSpider — no shared-behaviour
changes. `_items()` is overridden on this subclass only (not the shared
base) to add a strict price>0 guard: the base's own check (`if not
price: continue`) does not catch the string "0.00", which is truthy in
Python — a price of 0 is not an observation and must be dropped, not
shipped.
"""

from ._shopify_base import ShopifyBaseSpider


class AdeegSoSpider(ShopifyBaseSpider):
    name = "adeeg_so"
    allowed_domains = ["adeeg.com"]
    base_url = "https://adeeg.com"
    currency = "USD"
    language = "en"

    def _items(self, p: dict):
        for item in super()._items(p):
            try:
                price_val = float(item.get("price"))
            except (TypeError, ValueError):
                continue
            if price_val <= 0:
                continue
            yield item

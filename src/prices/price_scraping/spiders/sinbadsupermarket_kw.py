"""
Sinbad Supermarket (Kuwait) — https://sinbadsupermarket.com/.

Shopify storefront, standard /products.json catalog (no auth). Confirmed
live 2026-09-01: Shopify.country="KW", Shopify.currency.active="KWD"
(matches countries.yaml, no locality trap). 1,779 products across a genuine
grocery-led collection set (Grocery, Biscuits, Candy, Chips, Chocolates,
Coffee & Tea, Drinks, Frozen, Nuts, Pet Food & Supplies, plus
Cleaning/Household/Personal Care as normal supermarket departments) — a
real online supermarket, not scoped to a single category. Sample: "Maysa
Luncheon Meat Plain 800g" KWD 1.000, "Rita Canned Sweet Corn 400g" KWD
0.300 — 3-decimal KWD pricing, confirmed from the page (not assumed).

Distinct company/catalog from lulu_kw (Lulu Hypermarket, a different GCC
chain) and taw9eel_kw (a different platform entirely) — not the same shelf.
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class SinbadsupermarketKwSpider(ShopifyBaseSpider):
    name = "sinbadsupermarket_kw"
    allowed_domains = ["sinbadsupermarket.com"]
    base_url = "https://sinbadsupermarket.com"
    currency = "KWD"
    language = "en"

    def _items(self, p: dict):
        # One SKU ("Rose Premium Black Tea 100g") ships at price 0.000.
        # ShopifyBaseSpider._items guards with `if not price`, which does
        # NOT catch the string "0.000" - it is truthy. A zero is not a price
        # observation. Overridden here rather than in _shopify_base because
        # that base is shared with 65 live spiders in other countries.
        for item in super()._items(p):
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError, KeyError):
                pass
            yield item

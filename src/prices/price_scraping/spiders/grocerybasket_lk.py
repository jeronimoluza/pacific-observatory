"""
The Grocery Basket SL — thegrocerybasketsl.com, "Imported Baby Food &
Groceries in Sri Lanka".

Vanilla Shopify storefront — /products.json?limit=250&page=N, confirmed
1,250+ products across 5+ pages (curl_cffi impersonate=chrome124).
Shopify.currency active=LKR (confirmed inline).

Catalog skews toward imported/specialty snacks, cereals, condiments,
and baby food at premium prices (e.g. LKR 3,990 for an imported chip
bag) -- a real Sri Lankan storefront in LKR, but priced for the
imported/premium segment rather than mainstream local retail.
channel: specialty-food.

Uses the shared _shopify_base.ShopifyBaseSpider unmodified.

Verified live 2026-09-11: --max-items 100 run against page 1 produced
rows. Sample: "Takis Blue Heat Sharing Size Bag" LKR 3,990.00,
"Lajkonik Crunchy Salty Pretzels 130G" LKR 2,800.00.
"""

from ._shopify_base import ShopifyBaseSpider


class GrocerybasketLkSpider(ShopifyBaseSpider):
    name = "grocerybasket_lk"
    allowed_domains = ["thegrocerybasketsl.com"]
    base_url = "https://thegrocerybasketsl.com"
    currency = "LKR"
    language = "en"

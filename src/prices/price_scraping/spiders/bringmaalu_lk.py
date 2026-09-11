"""
Bring Maalu — bringmaalu.lk, "Buy Seafood Online Sri Lanka" ("maalu" =
fish in Sinhala).

Vanilla Shopify storefront — /products.json?limit=250&page=N, confirmed
145 products, single page. Shopify.currency active=LKR (confirmed
inline).

Premium/specialty seafood: caviar, live lobster, sashimi-grade salmon,
mud crab, prawns -- channel: specialty-food.

Uses the shared _shopify_base.ShopifyBaseSpider unmodified.

Verified live 2026-09-11: --max-items 100 run against page 1 produced
rows. Sample: "Kaspian Royal Malossol Caviar (30G)" LKR 44,000.00,
"U10 Lagoon Prawns Box (1KG)" LKR 3,600.00.
"""

from ._shopify_base import ShopifyBaseSpider


class BringmaaluLkSpider(ShopifyBaseSpider):
    name = "bringmaalu_lk"
    allowed_domains = ["bringmaalu.lk"]
    base_url = "https://bringmaalu.lk"
    currency = "LKR"
    language = "en"

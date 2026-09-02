"""Ospelt (Herbert Ospelt Anstalt / Malbuner) — https://shop.ospelt.com/.

Shopify storefront. Ospelt is headquartered in Bendern, LIECHTENSTEIN
(Schaanerstrasse 79, 9487 Bendern -- confirmed via the shop's own
schema.org PostalAddress JSON-LD, addressCountry "LI"). This is the
producer's own DIRECT-TO-CONSUMER webshop for its Malbuner-brand meat/deli
specialties (Rohschinken, Landjaeger, jerky, Le Parfait tinned meats) plus
gift baskets and merchandise -- a genuinely domestic Liechtenstein
retailer, not a Swiss chain, so the locality question does not apply here.

product_type "Box Builder" (144 of 367 raw variant rows on the 2026-09-01
run) is a build-your-own-gift-basket configurator: each "variant" is one
auto-generated combination the JS basket builder can produce, named e.g.
"Geschenkkorb (2 item(s) at 77.50: 2XvKxVi)" -- a cart-line summary, not a
distinct catalog item a shopper searches for. Shipping these would inflate
the row count with synthetic combinatorial noise and meaningless hashed
names, so this spider excludes that product_type entirely.
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider

# "Box Builder" is a build-your-own-gift-basket configurator whose "variants"
# are synthetic combinations, not SKUs. "filler" is Shopify layout furniture --
# nav tiles ("Geschenkideen", "Aktionen", "Merchandise") and section headers,
# all priced 0.00. Neither is a product.
_EXCLUDE_PRODUCT_TYPES = {"Box Builder", "filler"}


class OspeltLiSpider(ShopifyBaseSpider):
    name = "ospelt_li"
    allowed_domains = ["ospelt.com"]
    base_url = "https://shop.ospelt.com"
    currency = "CHF"
    language = "de"

    def _items(self, p: dict):
        if (p.get("product_type") or "") in _EXCLUDE_PRODUCT_TYPES:
            return
        for item in super()._items(p):
            # Free packaging and greeting-card add-ons ship at 0.00. A zero is
            # not a price observation, so drop rather than pollute the source.
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError, KeyError):
                pass
            yield item

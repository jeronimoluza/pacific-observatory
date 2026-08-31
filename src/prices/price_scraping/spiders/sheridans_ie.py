"""Sheridans Cheesemongers (Ireland) — https://sheridanscheesemongers.com/.

Shopify storefront. Galway-based specialty cheese, charcuterie and wine
shop. Two source-specific fixups over the shared `_shopify_base`:
- `product_type` is an empty string on every product here; the real
  taxonomy lives in `tags` (e.g. ["Deli", "Pate"], ["Red", "Wine"]) —
  used as the category when product_type is blank.
- A small share of listed "products" are event tickets (talks, festival
  entry) priced at 0.00; dropped.
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class SheridansIeSpider(ShopifyBaseSpider):
    name = "sheridans_ie"
    allowed_domains = ["sheridanscheesemongers.com"]
    base_url = "https://sheridanscheesemongers.com"
    currency = "EUR"
    language = "en"

    def _items(self, p):
        tags = p.get("tags") or []
        category = " / ".join(tags[:3]) if tags else None
        for item in super()._items(p):
            if float(item["price"]) <= 0:
                continue
            if not item.get("category") and category:
                item["category"] = category
            yield item

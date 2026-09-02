"""Happilo (India, Shopify) — https://www.happilo.com/

Specialty-food: dry fruits, nuts, seeds, and healthy snacks. /products.json
endpoint is open, no auth. Fills a specialty-food niche distinct from the
existing hypermarket (dmart_in) and supermarket (starquik) coverage.
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class HappiloInSpider(ShopifyBaseSpider):
    name = "happilo_in"
    allowed_domains = ["happilo.com", "www.happilo.com"]
    base_url = "https://www.happilo.com"
    currency = "INR"
    language = "en"

    def _items(self, p):
        # Opt-in filter, this subclass only: _shopify_base._items() checks
        # `if not price: continue`, which does not catch the string "0.00"
        # (truthy). A handful of happilo.com variants price at exactly 0
        # (likely unavailable/placeholder SKUs) and would otherwise ship as
        # zero-price rows.
        for item in super()._items(p):
            try:
                price = float(item.get("price") or 0)
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            yield item

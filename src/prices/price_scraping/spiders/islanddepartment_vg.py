"""
Island Department Store (British Virgin Islands) -- https://islanddepartment.store/.

Tortola furniture and home goods store.
Shopify storefront, open /products.json catalog; Shopify.currency.active = USD.
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class IslanddepartmentVgSpider(ShopifyBaseSpider):
    name = "islanddepartment_vg"
    allowed_domains = ["islanddepartment.store"]
    base_url = "https://islanddepartment.store"
    currency = "USD"
    language = "en"

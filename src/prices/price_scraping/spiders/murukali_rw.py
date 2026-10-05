"""Murukali (Rwanda, Shopify) -- https://murukali.com/.

The full /products.json feed starts with non-food marketplace items, so this
spider scopes the walk to the vegetables collection that was verified live on
2026-09-01 with current RWF prices for fresh produce.
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MurukaliRwSpider(ShopifyBaseSpider):
    name = "murukali_rw"
    allowed_domains = ["murukali.com"]
    base_url = "https://murukali.com"
    currency = "RWF"
    language = "en"
    PRODUCTS_PATH = "/collections/vegetables/products.json"

    def _items(self, product: dict):
        tags = product.get("tags") or []
        tag_text = " | ".join(str(tag).strip() for tag in tags if str(tag).strip())
        category = product.get("product_type") or tag_text or "Vegetables"
        for item in super()._items(product):
            item["category"] = category
            yield item

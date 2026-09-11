"""Configurable Shopify storefront crawler for generated price-source manifests."""

from ._shopify_base import ShopifyBaseSpider


class GenericShopifyConfiguredSpider(ShopifyBaseSpider):
    name = "generic_shopify_configured"

    def __init__(self, source_label=None, base_url=None, products_path="/products.json", currency=None, language="en", *args, **kwargs):
        super().__init__(*args, **kwargs)
        if source_label:
            self.source_label = source_label
        self.base_url = (base_url or self.base_url or "").rstrip("/")
        self.PRODUCTS_PATH = products_path or "/products.json"
        self.currency = currency or self.currency
        self.language = language or self.language
        domain = self.base_url.split("//", 1)[-1].split("/", 1)[0].replace("www.", "")
        self.allowed_domains = [domain] if domain else []

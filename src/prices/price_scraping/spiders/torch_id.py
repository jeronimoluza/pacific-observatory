"""Torch Indonesia bags, wallets, and travel apparel Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class TorchIdSpider(ShopifyBaseSpider):
    name = "torch_id"
    allowed_domains = ["torch.id"]
    base_url = "https://torch.id"
    currency = "IDR"
    language = "id"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}

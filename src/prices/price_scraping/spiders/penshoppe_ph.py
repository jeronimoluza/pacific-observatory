"""Penshoppe Philippines apparel, footwear, and accessories Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class PenshoppePhSpider(ShopifyBaseSpider):
    name = "penshoppe_ph"
    allowed_domains = ["penshoppe.com", "www.penshoppe.com"]
    base_url = "https://www.penshoppe.com"
    currency = "PHP"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}

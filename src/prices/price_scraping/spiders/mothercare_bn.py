"""Mothercare Brunei baby, nursery, and maternity Shopify catalog."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class MothercareBnSpider(ShopifyBaseSpider):
    name = "mothercare_bn"
    allowed_domains = ["mothercare-bn.com"]
    base_url = "https://mothercare-bn.com"
    currency = "BND"
    language = "en"

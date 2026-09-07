"""Baby Village Australia baby goods Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class BabyvillageAuSpider(ShopifyBaseSpider):
    name = "babyvillage_au"
    allowed_domains = ["www.babyvillage.com.au"]
    base_url = "https://www.babyvillage.com.au"
    currency = "AUD"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}

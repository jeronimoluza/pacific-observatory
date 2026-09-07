"""J-Lite Brunei computer parts and accessories Shopify catalog."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class JliteBnSpider(ShopifyBaseSpider):
    name = "jlitebn"
    allowed_domains = ["jlitebn.com"]
    base_url = "https://jlitebn.com"
    currency = "BND"
    language = "en"

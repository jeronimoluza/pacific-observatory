"""Frankie Wholesale Samoa Shopify wholesale grocery storefront."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class FrankieWholesaleWsSpider(ShopifyBaseSpider):
    name = "frankie_wholesale_ws"
    allowed_domains = ["frankiewholesale.ws", "www.frankiewholesale.ws"]
    base_url = "https://frankiewholesale.ws"
    currency = "WST"
    language = "en"

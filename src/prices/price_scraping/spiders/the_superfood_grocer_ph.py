"""The Superfood Grocer Philippines Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class TheSuperfoodGrocerPhSpider(ShopifyBaseSpider):
    name = "the_superfood_grocer_ph"
    allowed_domains = ["www.thesuperfoodgrocer.com", "thesuperfoodgrocer.com"]
    base_url = "https://www.thesuperfoodgrocer.com"
    currency = "PHP"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}

"""Salt + Light Home Guam furniture and home-goods catalog."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class SaltLightHomeGuamSpider(ShopifyBaseSpider):
    name = "salt_light_home_guam"
    allowed_domains = ["thesaltandlighthome.com", "www.thesaltandlighthome.com"]
    base_url = "https://thesaltandlighthome.com"
    currency = "USD"
    language = "en"

"""JB Hi-Fi Australia electronics, media, games, and accessories Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class JbhifiAuSpider(ShopifyBaseSpider):
    name = "jbhifi_au"
    allowed_domains = ["www.jbhifi.com.au"]
    base_url = "https://www.jbhifi.com.au"
    currency = "AUD"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}


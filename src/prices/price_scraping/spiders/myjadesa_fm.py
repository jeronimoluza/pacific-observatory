"""JADESA (Pohnpei, Federated States of Micronesia) — https://myjadesa.com

Shopify. /products.json?limit=250 open, 55 products (probed 2026-09-11). Shopify.currency
active=USD, which matches countries.yaml for FSM.
Pohnpei-based exporter/retailer: apparel and handicraft dominate (Pohnpei-print backpacks,
skirts, hoodies, bracelets) with a small local-food tail (Taro, Lepinkahs, Sele, black
pepper, coconut products). Channel is `other` rather than a food channel for that reason --
most of its value here is division 03 (clothing), which FSM has no other source for.
Page family parsed: API (/products.json).
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MyjadesaFmSpider(ShopifyBaseSpider):
    name = "myjadesa_fm"
    allowed_domains = ["myjadesa.com"]
    base_url = "https://myjadesa.com"
    currency = "USD"
    language = "en"

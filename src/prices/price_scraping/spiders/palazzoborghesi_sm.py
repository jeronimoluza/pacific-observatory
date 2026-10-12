"""Palazzo Borghesi -- https://palazzo-borghesi.com/ (fashion house, San Marino).

Shopify, open /products.json (84 products, EUR; Shopify.currency.active = EUR, probed 2026-10-12).
Page family: API.
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class PalazzoborghesiSmSpider(ShopifyBaseSpider):
    name = "palazzoborghesi_sm"
    allowed_domains = ["palazzo-borghesi.com"]
    base_url = "https://palazzo-borghesi.com"
    currency = "EUR"
    language = "it"

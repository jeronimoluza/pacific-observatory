"""Runway Couture & Shoetique (British Virgin Islands) -- https://runwayvi.com/.

Tortola women's fashion boutique (284 phone, pick-up policy). Shopify storefront,
open /products.json catalog (9 products at probe time); currency USD.
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class RunwayviVgSpider(ShopifyBaseSpider):
    name = "runwayvi_vg"
    allowed_domains = ["runwayvi.com"]
    base_url = "https://runwayvi.com"
    currency = "USD"
    language = "en"

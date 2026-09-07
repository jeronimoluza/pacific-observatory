"""Guam Boka Box Guam Snacks collection -- Shopify public catalog."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class GuamBokaBoxSpider(ShopifyBaseSpider):
    name = "guam_boka_box"
    allowed_domains = ["guambokabox.com", "www.guambokabox.com"]
    base_url = "https://www.guambokabox.com"
    currency = "USD"
    language = "en"
    PRODUCTS_PATH = "/collections/guam-snacks/products.json"

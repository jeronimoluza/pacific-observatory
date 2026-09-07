"""Guam Baby Company toys collection -- Shopify public catalog."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class GuamBabyCompanySpider(ShopifyBaseSpider):
    name = "guam_baby_company"
    allowed_domains = ["guambabyco.com", "www.guambabyco.com"]
    base_url = "https://guambabyco.com"
    currency = "USD"
    language = "en"
    PRODUCTS_PATH = "/collections/toys/products.json"

"""Banjoo SuperStore (Liberia) — WooCommerce storefront, Store API not exposed.

Monrovia general store delivering across Montserrado plus pickup in 12 towns.
"""

from __future__ import annotations

from ._woo_sitemap_base import WooSitemapBaseSpider


class BanjooLrSpider(WooSitemapBaseSpider):
    name = "banjoo_lr"
    allowed_domains = ["banjoosuperstore.com", "www.banjoosuperstore.com"]
    SITEMAP_URL = "https://banjoosuperstore.com/sitemap.xml"
    PRODUCT_URL_RE = r"/product/"
    currency = "USD"
    language = "en"

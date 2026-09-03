"""eBaaba (The Gambia) — online marketplace, JSON-LD product pages.

Gambia's largest online retailer; groceries alongside general merchandise.
"""

from __future__ import annotations

from ._woo_sitemap_base import WooSitemapBaseSpider


class EbaabaGmSpider(WooSitemapBaseSpider):
    name = "ebaaba_gm"
    allowed_domains = ["ebaaba.com", "www.ebaaba.com"]
    SITEMAP_URL = "https://www.ebaaba.com/sitemap.xml"
    PRODUCT_URL_RE = r"/product/"
    currency = "GMD"
    language = "en"

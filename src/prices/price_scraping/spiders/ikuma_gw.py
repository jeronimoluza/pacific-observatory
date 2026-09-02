"""Ikuma Online (Guinea-Bissau) — WooCommerce storefront, Store API disabled.

The Store API returns HTTP 500 on /products (categories work), so the product
sitemap is the enumerable surface. The PDP's JSON-LD emits the placeholder
currency "ABC", so XOF is forced.
"""

from __future__ import annotations

from ._woo_sitemap_base import WooSitemapBaseSpider


class IkumaGwSpider(WooSitemapBaseSpider):
    name = "ikuma_gw"
    allowed_domains = ["ikuma.online", "www.ikuma.online"]
    SITEMAP_URL = "https://www.ikuma.online/product-sitemap.xml"
    PRODUCT_URL_RE = r"/product/"
    currency = "XOF"
    FORCE_CURRENCY = "XOF"
    language = "pt"

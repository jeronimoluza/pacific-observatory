"""
GateGrocer (Kampala, Uganda) — https://gategrocer.com/.

Not WordPress: a bespoke server-rendered site whose product-detail pages each
carry a clean schema.org Product JSON-LD node (name, sku, category, offers.price,
offers.priceCurrency=UGX). The one flat /sitemap.xml lists every PDP under
/products/<slug>/, so the sitemap walker plus the shared JSON-LD parse chain is
all this needs.

PRODUCT_URL_RE requires at least one path segment after /products/ so the bare
/products/ listing page is not fetched as a product.
"""

from __future__ import annotations

from ._woo_sitemap_base import WooSitemapBaseSpider


class GategrocerUgSpider(WooSitemapBaseSpider):
    name = "gategrocer_ug"
    allowed_domains = ["gategrocer.com", "www.gategrocer.com"]
    SITEMAP_URL = "https://gategrocer.com/sitemap.xml"
    PRODUCT_URL_RE = r"/products/[^/]+/"
    currency = "UGX"
    language = "en"

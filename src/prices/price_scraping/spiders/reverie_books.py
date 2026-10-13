"""Reverie Books (Monrovia, Liberia) -- https://reveriebooks.shop/.

Re-platformed 2026-10 from WooCommerce to a custom Next.js storefront: the
WC Store API (/wp-json/wc/store/v1/products) now 404s. /sitemap.xml lists
~200 /product/<slug> PDPs, each with a server-rendered schema.org
Book/Product JSON-LD node carrying sku and an offers price in USD, e.g.
RBK-006 "48 Laws of Power" USD 17.00.
"""

from __future__ import annotations

from ._jsonld_sitemap_base import JsonLdSitemapBaseSpider


class ReverieBooksSpider(JsonLdSitemapBaseSpider):
    name = "reverie_books"
    allowed_domains = ["reveriebooks.shop"]
    SITEMAP_URL = "https://reveriebooks.shop/sitemap.xml"
    PRODUCT_URL_RE = r"/product/"
    currency = "USD"
    language = "en"

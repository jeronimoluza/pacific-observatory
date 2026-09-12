"""Eezzebuild (Botswana building materials) -- https://eezzebuild.co.bw/.

WooCommerce, but the Store API is firewalled: /wp-json/wc/store/v1/products
returns 401 on every call, so the generic_woo_configured route is unavailable.
The Yoast product sitemap is the enumerable surface instead --
/product-sitemap.xml lists 759 urls, of which 758 are /shop/<slug>/ PDPs (the
first loc is the bare /shop/ index and yields nothing).

Each PDP carries a WooCommerce JSON-LD Product node; WooBaseSpider.parse_html
reads it directly, so live and archived rows share one code path. Verified:
"Makoro Clay Stock Brick" BWP 3.17.

Page family: PDP only -- sitemap-driven.
"""

from __future__ import annotations

from ._woo_sitemap_base import WooSitemapBaseSpider


class EezzebuildBwSpider(WooSitemapBaseSpider):
    name = "eezzebuild_bw"
    allowed_domains = ["eezzebuild.co.bw"]
    SITEMAP_URL = "https://eezzebuild.co.bw/product-sitemap.xml"
    PRODUCT_URL_RE = r"/shop/[^/]+/"
    currency = "BWP"
    language = "en"

"""Poststore.ly (Libya) -- WooCommerce philatelic/collectibles storefront run by
Libya Post, WP REST API disabled site-wide.

WooCommerce Store API and wp-json are both unreachable (WP REST disabled), so
the product sitemap is the enumerable surface: 198 PDP urls, each carrying
OpenGraph product:price:amount / product:price:currency (LYD, verified live --
not the ikuma.online "ABC" placeholder bug, so no FORCE_CURRENCY needed).
"""

from __future__ import annotations

from ._woo_sitemap_base import WooSitemapBaseSpider


class PoststoreLySpider(WooSitemapBaseSpider):
    name = "poststore_ly"
    allowed_domains = ["poststore.ly", "www.poststore.ly"]
    SITEMAP_URL = "https://poststore.ly/product-sitemap.xml"
    PRODUCT_URL_RE = r"/product/"
    currency = "LYD"
    language = "ar"

"""Mbote Shop (Congo, Rep.) — marketplace with JSON-LD product pages.

Serves Brazzaville and Kinshasa; PDP JSON-LD prices in XAF, which is
Congo-Brazzaville's currency (Kinshasa/DRC transacts in CDF).
"""

from __future__ import annotations

from ._woo_sitemap_base import WooSitemapBaseSpider


class MboteCgSpider(WooSitemapBaseSpider):
    name = "mbote_cg"
    allowed_domains = ["mbote.shop", "www.mbote.shop"]
    SITEMAP_URL = "https://www.mbote.shop/sitemap.xml"
    PRODUCT_URL_RE = r"/p/"
    currency = "XAF"
    language = "fr"

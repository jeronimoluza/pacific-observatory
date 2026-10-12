"""Ormerco (Channel Islands) -- https://www.ormerco.com/. Wix store: store-products sitemap + schema.org JSON-LD per PDP."""

from __future__ import annotations

from ._jsonld_sitemap_base import JsonLdSitemapBaseSpider


class OrmercoCiSpider(JsonLdSitemapBaseSpider):
    name = "ormerco_ci"
    allowed_domains = ["www.ormerco.com", "ormerco.com"]
    SITEMAP_URL = "https://www.ormerco.com/store-products-sitemap.xml"
    PRODUCT_URL_RE = r"/product-page/"
    currency = "GBP"
    language = "en"

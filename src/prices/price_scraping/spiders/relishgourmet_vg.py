"""Relish Gourmet Food (British Virgin Islands) -- https://relishgourmetfood.com/.

Tortola/Virgin Gorda gourmet food, wine and beverage importer on an Ecwid
"starter site". sitemap.xml lists PDPs ending -p<id>; each PDP carries
schema.org Product JSON-LD with priceCurrency USD.
"""

from __future__ import annotations

from ._jsonld_sitemap_base import JsonLdSitemapBaseSpider


class RelishgourmetVgSpider(JsonLdSitemapBaseSpider):
    name = "relishgourmet_vg"
    allowed_domains = ["relishgourmetfood.com"]
    SITEMAP_URL = "https://relishgourmetfood.com/sitemap.xml"
    PRODUCT_URL_RE = r"-p\d+/?$"
    currency = "USD"
    language = "en"

"""BanguiStore -- https://banguistore.com/ (Bangui, Central African Republic).

Custom multi-vendor marketplace (phones, solar, IT, home). The product sitemap
lists every product three times (/fr/, /en/, /sg/); only /fr/ is followed so
each product is emitted once. PDPs carry a schema.org Product JSON-LD node with
priceCurrency XAF and sku.

Page family: PDP only -- sitemap-driven.
"""

from __future__ import annotations

from ._jsonld_sitemap_base import JsonLdSitemapBaseSpider


class BanguistoreCfSpider(JsonLdSitemapBaseSpider):
    name = "banguistore_cf"
    allowed_domains = ["banguistore.com"]
    SITEMAP_URL = "https://banguistore.com/sitemap.xml"
    PRODUCT_URL_RE = r"/fr/produits/"
    currency = "XAF"
    language = "fr"

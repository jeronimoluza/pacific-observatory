"""Quality Cuts Butchery E-Store (Kampala, Uganda) — https://qualitycuts.biz/.

WooCommerce, but the Store API route 404s (a 113-byte rest_no_route body), so
the sitemap is the enumerable surface: /sitemap.xml -> product-sitemap.xml with
605 PDPs under /product/<slug>/. Each PDP carries a schema.org Product node
whose `offers` is a LIST (the shared base already takes offers[0]) with
price + priceCurrency=UGX.
"""

from __future__ import annotations

from ._woo_sitemap_base import WooSitemapBaseSpider


class QualitycutsUgSpider(WooSitemapBaseSpider):
    name = "qualitycuts_ug"
    allowed_domains = ["qualitycuts.biz", "www.qualitycuts.biz"]
    SITEMAP_URL = "https://qualitycuts.biz/sitemap.xml"
    PRODUCT_URL_RE = r"/product/"
    currency = "UGX"
    language = "en"

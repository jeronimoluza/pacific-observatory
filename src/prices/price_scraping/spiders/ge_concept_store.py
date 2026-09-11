"""GE Concept Store (Central African Republic) -- https://www.ge-conceptstore.com/.

Wix storefront (WixStores app). Same route as nayelis_closet_gn: Wix's
sitemap index links a WIX-generated store-products-sitemap.xml (6 PDP urls --
small but real, no pagination needed), each PDP server-injecting schema.org
Product/offers JSON-LD. Verified priceCurrency "XAF" (Central African CFA
franc, correct for CAR).
"""

from __future__ import annotations

from ._jsonld_sitemap_base import JsonLdSitemapBaseSpider


class GeConceptStoreSpider(JsonLdSitemapBaseSpider):
    name = "ge_concept_store"
    allowed_domains = ["ge-conceptstore.com", "www.ge-conceptstore.com"]
    SITEMAP_URL = "https://www.ge-conceptstore.com/store-products-sitemap.xml"
    PRODUCT_URL_RE = r"/product-page/"
    currency = "XAF"
    language = "fr"

"""TechSight Eyewear (Liberia) -- https://www.techsightinc.com/.

Wix storefront (WixStores app). Same route as nayelis_closet_gn/commbeauty:
Wix's sitemap index links a WIX-generated store-products-sitemap.xml (14 PDP
urls), each PDP server-injecting schema.org Product/offers JSON-LD.
"""

from __future__ import annotations

from ._jsonld_sitemap_base import JsonLdSitemapBaseSpider


class TechsightEyewearSpider(JsonLdSitemapBaseSpider):
    name = "techsight_eyewear"
    allowed_domains = ["techsightinc.com", "www.techsightinc.com"]
    SITEMAP_URL = "https://www.techsightinc.com/store-products-sitemap.xml"
    PRODUCT_URL_RE = r"/product-page/"
    currency = "USD"
    language = "en"

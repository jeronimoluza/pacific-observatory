"""CommBeauty (Liberia) -- https://www.commbeauty.com/.

Wix storefront (WixStores app). Same route as nayelis_closet_gn: Wix's
sitemap index links a WIX-generated store-products-sitemap.xml (73 PDP urls),
and each PDP server-injects schema.org Product/offers JSON-LD.
"""

from __future__ import annotations

from ._jsonld_sitemap_base import JsonLdSitemapBaseSpider


class CommbeautySpider(JsonLdSitemapBaseSpider):
    name = "commbeauty"
    allowed_domains = ["commbeauty.com", "www.commbeauty.com"]
    SITEMAP_URL = "https://www.commbeauty.com/store-products-sitemap.xml"
    PRODUCT_URL_RE = r"/product-page/"
    currency = "USD"
    language = "en"

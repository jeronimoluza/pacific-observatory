"""Pacific Supply Co (Marshall Islands) -- https://www.pacificsupplyco.online/.

Wix storefront (WixStores app). Same route as nayelis_closet_gn: sitemap.xml
-> store-products-sitemap.xml (40 PDP urls) -> schema.org JSON-LD per PDP.
"""

from __future__ import annotations

from ._jsonld_sitemap_base import JsonLdSitemapBaseSpider


class PacificSupplyCoFurnitureSpider(JsonLdSitemapBaseSpider):
    name = "pacific_supply_co_furniture"
    allowed_domains = ["pacificsupplyco.online", "www.pacificsupplyco.online"]
    SITEMAP_URL = "https://www.pacificsupplyco.online/store-products-sitemap.xml"
    PRODUCT_URL_RE = r"/product-page/"
    currency = "USD"
    language = "en"

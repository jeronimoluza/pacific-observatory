"""V.I. Crown (British Virgin Islands) -- https://vicrown.store/.

Tortola (BVI) clothing brand.
Wix storefront (WixStores). sitemap.xml links a WIX-generated
store-products-sitemap.xml; each PDP server-injects schema.org Product/offers
JSON-LD (priceCurrency USD read from the page). Page family: PDP.
"""

from __future__ import annotations

from ._jsonld_sitemap_base import JsonLdSitemapBaseSpider


class VicrownVgSpider(JsonLdSitemapBaseSpider):
    name = "vicrown_vg"
    allowed_domains = ["vicrown.store", "www.vicrown.store"]
    SITEMAP_URL = "https://www.vicrown.store/store-products-sitemap.xml"
    PRODUCT_URL_RE = r"/product-page/"
    currency = "USD"
    language = "en"

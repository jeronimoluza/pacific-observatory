"""DLux Cosmetics BVI (British Virgin Islands) -- https://dluxcosmeticsbvi.com/.

Tortola cosmetics and skincare retailer.
Wix storefront (WixStores). sitemap.xml links a WIX-generated
store-products-sitemap.xml; each PDP server-injects schema.org Product/offers
JSON-LD (priceCurrency USD read from the page). Page family: PDP.
"""

from __future__ import annotations

from ._jsonld_sitemap_base import JsonLdSitemapBaseSpider


class DluxcosmeticsbviVgSpider(JsonLdSitemapBaseSpider):
    name = "dluxcosmeticsbvi_vg"
    allowed_domains = ["dluxcosmeticsbvi.com", "www.dluxcosmeticsbvi.com"]
    SITEMAP_URL = "https://www.dluxcosmeticsbvi.com/store-products-sitemap.xml"
    PRODUCT_URL_RE = r"/product-page/"
    currency = "USD"
    language = "en"

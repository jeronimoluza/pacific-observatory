"""Body Glam Cosmetics (British Virgin Islands) -- https://bodyglamcosmetics.com/.

BVI body-care and cosmetics maker/retailer.
Wix storefront (WixStores). sitemap.xml links a WIX-generated
store-products-sitemap.xml; each PDP server-injects schema.org Product/offers
JSON-LD (priceCurrency USD read from the page). Page family: PDP.
"""

from __future__ import annotations

from ._jsonld_sitemap_base import JsonLdSitemapBaseSpider


class BodyglamcosmeticsVgSpider(JsonLdSitemapBaseSpider):
    name = "bodyglamcosmetics_vg"
    allowed_domains = ["bodyglamcosmetics.com", "www.bodyglamcosmetics.com"]
    SITEMAP_URL = "https://www.bodyglamcosmetics.com/store-products-sitemap.xml"
    PRODUCT_URL_RE = r"/shop-1/"
    currency = "USD"
    language = "en"

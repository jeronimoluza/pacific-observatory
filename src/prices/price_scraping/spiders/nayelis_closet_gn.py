"""Nayeli's Closet (Guinea) -- https://www.nayelicloset.com/.

Wix storefront (WixStores app) -- not Shopify/Woo/Presta/OpenCart, and Wix's
ecommerce storefront API (/_api/wix-ecommerce-storefront-web/api) requires an
instance token this spider doesn't have, so the enumerable surface is Wix's
own product sitemap: /sitemap.xml (a WIX-generated sitemapindex) points at
/store-products-sitemap.xml, which lists 830 PDP urls. Each PDP is a Wix SPA
shell, but Wix server-injects a standard schema.org Product/offers JSON-LD
block for SEO that survives a plain HTTP GET (verified live: priceCurrency
"GNF", matching Guinea's own currency).
"""

from __future__ import annotations

from ._jsonld_sitemap_base import JsonLdSitemapBaseSpider


class NayelisClosetGnSpider(JsonLdSitemapBaseSpider):
    name = "nayelis_closet_gn"
    allowed_domains = ["nayelicloset.com", "www.nayelicloset.com"]
    SITEMAP_URL = "https://www.nayelicloset.com/store-products-sitemap.xml"
    PRODUCT_URL_RE = r"/product-page/"
    currency = "GNF"
    language = "fr"

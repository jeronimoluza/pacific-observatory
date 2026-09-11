"""Atuagkat (Greenland) -- https://sinemalu.wixsite.com/my-site-1.

Greenlandic bookstore on a free wixsite.com subdomain (not a custom domain,
but a real business -- "Atuagkat" is a known Nuuk bookshop). Wix storefront,
same route as nayelis_closet_gn: sitemap.xml -> store-products-sitemap.xml
(419 PDP urls) -> schema.org JSON-LD per PDP, verified priceCurrency "DKK"
(Danish Krone, Greenland's actual currency -- not EUR, the common diaspora-
pricing trap this batch was warned about).
"""

from __future__ import annotations

from ._jsonld_sitemap_base import JsonLdSitemapBaseSpider


class AtuagkatGlSpider(JsonLdSitemapBaseSpider):
    name = "atuagkat_gl"
    allowed_domains = ["sinemalu.wixsite.com"]
    SITEMAP_URL = "https://sinemalu.wixsite.com/my-site-1/store-products-sitemap.xml"
    PRODUCT_URL_RE = r"/product-page/"
    currency = "DKK"
    language = "kl"

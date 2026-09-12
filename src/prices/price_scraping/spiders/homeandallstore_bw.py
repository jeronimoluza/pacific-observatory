"""Home & All Store (Gaborone) -- https://www.homeandallstore.online/.

Wix storefront. The category pages are a client-rendered SPA shell, but Wix
server-injects schema.org Product JSON-LD into each PDP for SEO, so a plain
HTTP GET is enough and Playwright is never needed.

Enumerable surface: /store-products-sitemap.xml (Wix-generated), 155
/product-page/ urls. priceCurrency on the PDP JSON-LD reads BWP -- verified,
not assumed: "Electronic Fitness Skipping Rope with Counter" BWP 199.74.

Page family: PDP only -- sitemap-driven, never fetches a listing page.
"""

from __future__ import annotations

from ._jsonld_sitemap_base import JsonLdSitemapBaseSpider


class HomeandallstoreBwSpider(JsonLdSitemapBaseSpider):
    name = "homeandallstore_bw"
    allowed_domains = ["homeandallstore.online"]
    SITEMAP_URL = "https://www.homeandallstore.online/store-products-sitemap.xml"
    PRODUCT_URL_RE = r"/product-page/"
    currency = "BWP"
    language = "en"

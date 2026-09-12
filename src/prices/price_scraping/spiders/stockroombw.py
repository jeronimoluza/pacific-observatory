"""Stockroom BW (Gaborone) -- https://www.stockroombw.com/.

Wix storefront, same route as homeandallstore_bw: the Wix-generated
/store-products-sitemap.xml lists 35 /product-page/ urls and each PDP carries
a server-injected schema.org Product JSON-LD node with priceCurrency BWP.
Verified: "Kids All Star T-Shirt" BWP 99.14.

GOTCHA: a minority of PDPs carry a placeholder offer price of 1.00 (seen on
"African Black Shirt (Tribes Print)"). These are unlisted-price items, not
BWP 1 goods -- worth a downstream sanity filter on this source.

Page family: PDP only -- sitemap-driven.
"""

from __future__ import annotations

from ._jsonld_sitemap_base import JsonLdSitemapBaseSpider


class StockroombwSpider(JsonLdSitemapBaseSpider):
    name = "stockroombw"
    allowed_domains = ["stockroombw.com"]
    SITEMAP_URL = "https://www.stockroombw.com/store-products-sitemap.xml"
    PRODUCT_URL_RE = r"/product-page/"
    currency = "BWP"
    language = "en"

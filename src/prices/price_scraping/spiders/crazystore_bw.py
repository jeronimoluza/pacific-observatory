"""The Crazy Store Botswana -- https://www.crazystore.co.bw/.

Variety / discount chain (housewares, stationery, toys, party, hardware,
pet, confectionery) with 7,053 PDP urls in its own .co.bw sitemap. PDPs
carry a schema.org Product JSON-LD node with name, sku and offers, and the
priceCurrency on that node reads BWP -- verified on two PDPs, e.g.
301-005131-B "100 Bulb String Light Cool White, 10m" BWP 109.99.

GOTCHA: the tenant runs one storefront per country and robots.txt on the
.co.bw host advertises the .co.za sitemap. Following robots.txt hands you
7,053 crazystore.co.za urls priced in ZAR, which look like a passing probe
and are the wrong country. Fetch https://www.crazystore.co.bw/sitemap.xml
DIRECTLY -- it is a flat urlset with no sitemapindex, it lists .co.bw urls,
and those PDPs return BWP.

Page family: PDP only -- sitemap-driven, the spider never fetches a listing.
"""

from __future__ import annotations

from ._jsonld_sitemap_base import JsonLdSitemapBaseSpider


class CrazystoreBwSpider(JsonLdSitemapBaseSpider):
    name = "crazystore_bw"
    allowed_domains = ["crazystore.co.bw"]
    SITEMAP_URL = "https://www.crazystore.co.bw/sitemap.xml"
    PRODUCT_URL_RE = r"/products/"
    currency = "BWP"
    language = "en"

"""JTCSTORE (St Lucia) -- https://www.jtcstore.com/.

St Lucia's second independent food/grocery source (first: massy_stores_slu).
Genuine local online grocery retailer -- physical distribution/retail point
at Best Buy, Bridge Street, Castries (opposite the General Post Office),
open 9am-4pm weekdays / 9am-1pm Saturday; not a diaspora-shipping site. Sells
Caribbean, Indian, Chinese, Middle Eastern and Italian grocery items
alongside common supermarket staples.

Despite the domain name, this is a Wix site (NOT WordPress) -- WooCommerce
Store API probes (`/wp-json/wc/store/v1/products`, `?rest_route=`) both
404/no-op. Same route as atuagkat_gl / nayelis_closet_gn: `sitemap.xml` ->
`store-products-sitemap.xml` (665 PDP urls, `/product-page/<slug>`) -> each
PDP server-renders a schema.org `Product` JSON-LD block for SEO even though
the page itself is a client-rendered Wix SPA shell.

Verified live 2026-09-11: sample PDP `/product-page/laxmi-ajwain-seeds-400-gm`
-> 200, JSON-LD `{"name": "LAXMI AJWAIN SEEDS 400 GM", "sku": "18115211003",
"offers": {"priceCurrency": "XCD", "price": "25.1", "availability":
".../InStock"}}`. Currency XCD is read directly from the JSON-LD payload
(matches countries.yaml st_lucia, not inferred from a "$" glyph).
curl_cffi impersonate="chrome124" clears every path with no WAF encountered.
"""

from __future__ import annotations

from ._jsonld_sitemap_base import JsonLdSitemapBaseSpider


class JtcstoreSluSpider(JsonLdSitemapBaseSpider):
    name = "jtcstore_slu"
    allowed_domains = ["www.jtcstore.com", "jtcstore.com"]
    SITEMAP_URL = "https://www.jtcstore.com/store-products-sitemap.xml"
    PRODUCT_URL_RE = r"/product-page/"
    currency = "XCD"
    language = "en"

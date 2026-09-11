"""
Carrefour Italia -- https://www.carrefour.it/.

Different platform from carrefour_fr.py's Salesforce-style rayon HTML: no
Akamai/Cloudflare WAF here at all -- bare `curl` (no TLS impersonation)
clears the sitemap AND every product-detail page at 200. A custom
sitemap_index.xml lists 6 shards (`sitemap_0-product.xml` through
`sitemap_3.xml`, plus category/content/stores/volantini); the product shard
is a flat urlset, not a further-nested index -- 26,430 `/p/<slug>/<ean>.html`
URLs, ALL matching that shape (0 non-matching sampled across the whole
file), so PRODUCT_URL_RE is unnecessary; SITEMAP_URL points straight at the
product-only shard.

Each PDP embeds a clean Schema.org Product JSON-LD node
(offers.price/priceCurrency, single dict, not a list). Verified live
2026-09-10 on 5 URLs spread across the file (positions 1, 5000, 10000,
20000, 26000): all 5 EUR, e.g. "Sant'Anna Pet Lt 2,0X6 Naturale" EUR 3.96,
"Terre d'Italia Salamini Italiani alla Cacciatora DOP 100 g" EUR 3.85.
Some rows carry `availability: OutOfStock` but still a real price -- kept,
since `WooBaseSpider._item`/`_woo_row_from_product_node` records price
regardless of stock state and only drops price<=0.
"""

from ._woo_sitemap_base import WooSitemapBaseSpider


class CarrefourItSpider(WooSitemapBaseSpider):
    name = "carrefour_it"
    allowed_domains = ["carrefour.it"]
    currency = "EUR"
    language = "it"
    SITEMAP_URL = "https://www.carrefour.it/sitemap_0-product.xml"
    PRODUCT_URL_RE = r"/p/[^/]+/\d+\.html$"

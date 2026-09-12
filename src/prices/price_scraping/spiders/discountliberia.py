"""Discount Liberia -- https://discountliberia.com/

Monrovia general-merchandise storefront ("Discount Liberia"), a PHP/nginx
custom storefront behind Cloudflare (the page markup mentions OpenCart, but
none of the OpenCart routes exist -- product URLs are
/products/details/<slug>, so the OpenCart base spider does not apply).

Probed live 2026-09-12 with curl_cffi impersonate=chrome124:
  * home 200, /sitemap.xml 200 with 3,342 <loc> entries, of which 3,325 are
    /products/details/<slug> product pages (the rest are category, seller and
    static pages) -- that is the enumeration route, no gallery pagination
    needed.
  * every PDP is server-rendered with a schema.org Product JSON-LD block, so
    the repo's shared rows_from_jsonld helper parses it unchanged. Verified
    against the real helper, not by eye:
      {'product_name': 'New Huion KAMVAS 22 ... Graphic Tablet with Stylus',
       'price': '493.9', 'currency': 'USD', 'category': 'Phones & Tablets'}
    -- note the JSON-LD even carries the breadcrumb category, which most
    sources in this directory do not.

CURRENCY: USD, read off the PDP's own JSON-LD priceCurrency. Liberia is a
dual-currency USD/LRD economy, so this is flagged rather than assumed.

Page family parsed: PDP (JSON-LD on /products/details/<slug>).
"""

from ._jsonld_sitemap_base import JsonLdSitemapBaseSpider


class DiscountliberiaSpider(JsonLdSitemapBaseSpider):
    name = "discountliberia"
    allowed_domains = ["discountliberia.com"]
    currency = "USD"
    language = "en"

    SITEMAP_URL = "https://discountliberia.com/sitemap.xml"
    PRODUCT_URL_RE = r"/products/details/"

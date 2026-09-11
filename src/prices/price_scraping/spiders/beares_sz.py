"""
Beares Eswatini (furniture & appliances) - beares.co.sz.

Magento 2 storefront. /graphql is Cloudflare Turnstile-protected on every
curl_cffi profile (chrome124/120/131/133a, safari17_0 all 403 "Just a
moment..."), so this uses MagentoSSRBaseSpider against the server-rendered
Luma-theme category HTML instead -- confirmed open, no challenge.

Gotcha: the apex domain (beares.co.sz) silently drops the ?p=2 pagination
query param (page 2 re-serves page 1 verbatim); the www. subdomain
paginates correctly (0 overlap between page 1 and page 2 of the
"shop-by-product" hub, 195 total products). allowed_domains and
DISCOVERY_URL both use www.

Discovery: the homepage's linked categories rotate per visit (banner-driven),
so it is not a stable seed. /media/sitemap.xml on this domain is stable
but its <loc> entries are hardcoded to the beares.co.za (South Africa)
tenant -- a shared static asset across the group's country storefronts, not
evidence this is the wrong site. CATEGORY_URL_RE captures only the path
after the .co.za host and lets response.urljoin (against the .sz sitemap
URL) rebuild it on this domain -- confirmed the .sz paths resolve with real
product-item-link/data-price-amount markup (e.g.
/shop-by-room/kitchen/fridge-freezers). 61 category paths found this way,
spanning furniture, appliances and electronics.

SZL prices confirmed via <meta property="product:price:currency" content="SZL">
and store=en_sz in image URLs on the product-detail page.

product_id override: the base class's default (last URL path segment) is
wrong for this tenant's long-form PDP URLs
(.../catalog/product/view/id/1744/s/<slug>/category/173/) -- the trailing
segment is the *category* id (173), not the product id (1744), so every
product in a category would otherwise carry an identical, misleading
product_id. Pull the real id out of the /id/<N>/ segment when present;
fall back to the base behaviour for this tenant's short-form SEO URLs
(.../347l-fridge-with-water-dispenser), which have no /id/ segment and
whose slug is already a real per-product identifier.
"""

import re

from price_scraping.spiders._magento_base import MagentoSSRBaseSpider

_ID_RE = re.compile(r"/id/(\d+)/")


class BearesSzSpider(MagentoSSRBaseSpider):
    name = "beares_sz"
    allowed_domains = ["www.beares.co.sz"]
    currency = "SZL"
    language = "en"
    DISCOVERY_URL = "https://www.beares.co.sz/media/sitemap.xml"
    CATEGORY_URL_RE = re.compile(
        r"<loc>https://www\.beares\.co\.za(/shop-by-(?:room|product)/[^<]+)</loc>"
    )

    def _item(self, url, name, price):
        item = super()._item(url, name, price)
        if item:
            m = _ID_RE.search(url)
            if m:
                item["product_id"] = m.group(1)
        return item

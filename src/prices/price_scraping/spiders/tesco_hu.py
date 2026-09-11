"""Tesco Hungary -- https://bevasarlas.tesco.hu/ (Tesco's own Hungarian
storefront -- NOT the Wolt-delivery `tesco_wolt_sk`/`tesco_wolt_cz` sources
already in this repo, which are a single physical branch each on a different
platform/channel).

One of a 4-country Tesco-storefront batch (CZ/HU/IE/UK). Only HU shipped --
see `known_blockers_batch_7.md` for why nakup.itesco.cz, tesco.ie and
tesco.com were not: their product-detail endpoint returns a hard Akamai
edge deny (or a client-side JS proof-of-work interstitial) on every
curl_cffi TLS profile tried (chrome120/124/131/150) AND on headless
Playwright, even though their *homepage* and sitemap XML are reachable.
HU's product endpoint is not behind that wall.

robots.txt -> https://bevasarlas.tesco.hu/sitemaps/hu-HU/groceries/products-index.xml
-> a <sitemapindex> of 4 shards (products-1..4.xml, 5,000 <loc> each,
~19,376 products per the campaign's sitemap count). Verified live
2026-09-10: shard 1 and shard 2 are DISJOINT (5,000 URLs each, 0 overlap).
Product URL shape: /shop/hu-HU/products/<numeric id>.

No TLS-profile override needed -- the repo's default pinned `chrome120`
profile works. The PDP endpoint IS behind Akamai Bot Manager (`_abck`,
`bm_sz`, `ak_bmsc` cookies), but the very first request of the crawl (the
sitemap-index fetch) already receives and sets those cookies via ordinary
Set-Cookie headers, and Scrapy's default CookiesMiddleware (COOKIES_ENABLED
= True repo-wide) carries them into every later same-domain request --
confirmed live: an isolated curl_cffi session that fetches only a sitemap
shard first, then a product page with NO separate warm-up visit and NO
referer header, gets a real 200 with product JSON-LD every time. A product
page requested as the very first request of a cold session 403s.

Each PDP embeds one `<script type="application/ld+json">` whose `@graph`
contains a `Product` node (name, sku, offers.price, offers.priceCurrency) --
parsed by the shared `WooBaseSpider.parse_html` JSON-LD chain (this tenant
is not WooCommerce; the sitemap+JSON-LD shape is identical, same convention
already used by `auchan_hu`, `alcampo_es`, etc. in this repo).

**Currency bug, confirmed on 8/8 sampled PDPs across both shards**: every
product's JSON-LD reports `"priceCurrency":"GBP"` regardless of the actual
HUF price -- e.g. "Andrea Milano Deto bio szuretlen almaecet 500 ml" (a
Hungarian apple-cider vinegar) at `price=2599`, which is a plausible HUF
price (~7 USD) and an absurd GBP one. FORCE_CURRENCY="HUF" overrides it;
HUF matches `src/configs/countries.yaml` for Hungary and is not a
zero-decimal-ambiguous currency issue since Tesco's own price field is
already a bare integer (HUF has no minor unit).

Sample rows (live, 2026-09-10): 'Andrea Milano Deto bio szuretlen almaecet
500 ml' HUF 2599 (InStock); 'Parmalat Smoothie almas, oszibarackos, lime-os
zsirszegeny savanyu tejkeszitmeny spirulinaval 330 g' HUF 629 (InStock);
'F&F Brazil fazonu alsonemu, 5 db/csomag 38' HUF 5090 (OutOfStock -- kept,
not dropped; availability is recorded, not gate-kept here).
"""

from __future__ import annotations

from ._woo_sitemap_base import WooSitemapBaseSpider


class TescoHuSpider(WooSitemapBaseSpider):
    name = "tesco_hu"
    allowed_domains = ["bevasarlas.tesco.hu"]
    SITEMAP_URL = (
        "https://bevasarlas.tesco.hu/sitemaps/hu-HU/groceries/products-index.xml"
    )
    PRODUCT_URL_RE = r"/shop/hu-HU/products/\d+"
    currency = "HUF"
    FORCE_CURRENCY = "HUF"
    language = "hu"

    # Real anti-bot stack (Akamai Bot Manager) -- stay well under the base's
    # already-cautious defaults (CONCURRENT_REQUESTS_PER_DOMAIN=2,
    # DOWNLOAD_DELAY=1.0). A burst risks tripping the same behavioral
    # challenge that hard-blocks the CZ/IE/UK product endpoints.
    custom_settings = {
        **WooSitemapBaseSpider.custom_settings,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.5,
    }

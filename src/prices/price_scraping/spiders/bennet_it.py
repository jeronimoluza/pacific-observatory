"""
Bennet (Italy) -- https://www.bennet.com/, large Italian hypermarket chain.

SAP Commerce (Hybris) storefront behind Akamai. Plain `curl` (no TLS
impersonation) 403s on everything -- robots.txt, sitemap.xml, PDPs alike --
with the standard `errors.edgesuite.net` stub, but `curl_cffi` clears at 200
on EVERY tried profile including the repo-pinned default `chrome120`
(verified 2026-09-10: chrome124/chrome120/chrome131/safari17_0/
chrome131_android all 200), so no IMPERSONATE_PROFILE override is needed.

robots.txt declares `Crawl-delay: 10` and a `Visit-time: 0400-0845` (UTC)
crawl window -- ROBOTSTXT_OBEY is repo-wide False so this isn't auto
enforced, but DOWNLOAD_DELAY is set to 10.0 here out of caution (large site,
real anti-bot budget per the wave-2 addendum) and the visit-time window is
worth honoring when this source's cadence/cron is scheduled -- see YAML
notes.

`sitemap.xml` is a genuine `<sitemapindex>`: one `Homepage-it-EUR-*.xml`
entry plus 21 `ProductSolr-it-EUR-<n>-*.xml` shards, each ~1,000 URLs.
Verified live: shard 0 vs shard 1 are 1000/1000 URLs with ZERO overlap.
Product URL shape is `.../p/P_<digits>` or `.../p/B_<digits>` (bundle SKUs),
sometimes without a `/Categories/` path segment -- confirmed 0 of 20,582
URLs across all 21 shards fail to match `/p/[A-Z]_\\d+$`, so that's the
PRODUCT_URL_RE rather than anything tied to `/Categories/`.

Each PDP embeds a Schema.org Product JSON-LD node with a single-dict
`offers` (price/priceCurrency/availability, no list). Verified live on 5
URLs across shard 0 and shard 1: all EUR, e.g. "Tombolino 3 Zip" EUR 19.90,
"Boxer Uomo Classic Cotone Multielasticizzato 5 Nero Liabel" EUR 5.90.

_woo_sitemap_base.parse_sitemap classifies a `<loc>` as a child sitemap via
`u.lower().endswith(".xml")` on the raw URL string. Every shard URL here
carries a `?context=<base64>` query string after `.xml`
(`.../ProductSolr-it-EUR-0-....xml?context=...`), so the base class's own
check never fires -- it saw urls=28 child_maps=0 products=0 against the
live index. Not a file this batch owns (`_woo_sitemap_base.py` is shared),
so this overrides `parse_sitemap` here instead of patching the base: same
depth-gated walk, just strips the query string before testing `.xml`.
"""

from ._woo_sitemap_base import WooSitemapBaseSpider


class BennetItSpider(WooSitemapBaseSpider):
    name = "bennet_it"
    allowed_domains = ["bennet.com"]
    currency = "EUR"
    language = "it"
    SITEMAP_URL = "https://www.bennet.com/sitemap.xml"
    PRODUCT_URL_RE = r"/p/[A-Z]_\d+$"

    custom_settings = {
        **WooSitemapBaseSpider.custom_settings,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 10.0,
    }


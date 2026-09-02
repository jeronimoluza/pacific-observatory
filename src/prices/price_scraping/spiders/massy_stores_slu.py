"""
Massy Stores St. Lucia -- https://www.shopmassystoresslu.com/.

Separate WooCommerce tenant from massy_stores_bb (Barbados) and
massy_stores_tt (Trinidad) -- distinct catalog/currency per territory.
Same non-standard install as Barbados: the default
/wp-json/wc/store/v1/products path 500s ("WordPress > Error"); the
?rest_route= query-string form works instead.

WAF note: the repo-wide pinned curl_cffi profile (chrome120) 403s on this
tenant, as does chrome124/chrome131/chrome99. safari17_0 clears it (200).

Gotcha found while onboarding this source: setting only IMPERSONATE_PROFILE
is NOT enough. scrapy_impersonate's RandomBrowserMiddleware
(process_request) unconditionally overwrites request.meta["impersonate"]
with a random pick from settings.py's IMPERSONATE_BROWSERS pool on every
request -- it does not check whether the spider already set a value -- so
IMPERSONATE_PROFILE alone is silently clobbered back to chrome120 and the
run 403s. The fix (already an established pattern in this repo, see
cassandraonlinemarket_ht.py) is to disable that one middleware via
custom_settings for just this spider, which also means the User-Agent
header must be swapped to match the safari17_0 TLS fingerprint --
curl_cffi forwards Scrapy's headers verbatim, so a chrome120 UA paired
with a safari17_0 handshake is itself a mismatched fingerprint. Neither
change touches settings.py or _woo_base.py -- both are scoped to this
subclass only via the existing IMPERSONATE_PROFILE opt-in hook.

Second bug found: WooBaseSpider._item() only checks `prices.get("price") is
None` -- it does not guard against a zero price, and this tenant genuinely
emits price="0" for a handful of listings (out-of-stock/discontinued SKUs
left at a placeholder price rather than removed from the catalog; confirmed
7 of 7851 rows in the first full run, e.g. "Local Produce Sweet Pepper (per
KG)" and "Snickers King Size (Each)" both at 0.00 XCD). A price of 0 is not
an observation. Fixed here, NOT in the shared base class, by overriding
_item() to drop any row whose numeric price is <= 0 after the base class's
minor-unit conversion -- `if not price` would NOT catch this (a "0.00"
string, or the float 0.0, is falsy either way here since the base class
already returns a str(value), but the general trap is that "0.00" as a bare
string is truthy while float(price) <= 0 is the correct numeric guard).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class MassyStoresSluSpider(WooBaseSpider):
    name = "massy_stores_slu"
    allowed_domains = ["shopmassystoresslu.com", "www.shopmassystoresslu.com"]
    currency = "XCD"
    language = "en"
    custom_settings = {
        **WooBaseSpider.custom_settings,
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Safari/605.1.15"
        ),
    }
    IMPERSONATE_PROFILE = "safari17_0"
    BASE_URL = "https://www.shopmassystoresslu.com/?rest_route=/wc/store/v1/products"

    def _item(self, p: dict):
        item = super()._item(p)
        if item is None:
            return None
        try:
            price = float(item["price"])
        except (TypeError, ValueError):
            return None
        if price <= 0:
            return None
        return item

"""
Kalico (Grenada) -- https://kalico.gd/.

Standard WooCommerce Store API. XCD prices at currency_minor_unit=2
(e.g. price "508" -> $5.08), currency_code confirmed as "XCD" directly from
the Store API response.

Enumerability confirmed: per_page=50 page 1 vs page 2 -> 50/50 rows, 0 SKU
overlap.

The repo-wide pinned curl_cffi profile (settings.py IMPERSONATE_BROWSERS,
chrome120) gets a 403 from this tenant's WAF; chrome123/chrome124/
safari17_0 all clear it (confirmed live 2026-09-11). Disable the
random-profile middleware just for this spider and pin chrome124 via
_woo_base's IMPERSONATE_PROFILE hook, matching the User-Agent header to the
same Chrome version (a chrome124 TLS handshake with a chrome120 UA string
is itself a mismatched fingerprint) -- same pattern as
cassandraonlinemarket_ht.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class KalicoGdSpider(WooBaseSpider):
    name = "kalico_gd"
    allowed_domains = ["kalico.gd"]
    currency = "XCD"
    language = "en"
    BASE_URL = "https://kalico.gd/wp-json/wc/store/v1/products"

    custom_settings = {
        **WooBaseSpider.custom_settings,
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }
    IMPERSONATE_PROFILE = "chrome124"

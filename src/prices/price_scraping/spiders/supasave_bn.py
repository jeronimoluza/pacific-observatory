"""
Supa Save (Brunei) -- https://seria.supasave.com.bn/.

Brunei's main supermarket chain. Standard WooCommerce Store API,
BND prices at currency_minor_unit=2 (e.g. price "400" -> $4.00), confirmed
against the site's own price_html on the same row.

The main `supasave.com.bn` domain and the `seria.supasave.com.bn` subdomain
were both previously recorded blocked (sgcaptcha stub, probed 2026-06-10).
Re-probed 2026-09-06: the repo-wide pinned curl_cffi profile (settings.py
IMPERSONATE_BROWSERS, chrome120) still gets a 403 "Forbidden" from
seria.supasave.com.bn -- but chrome124, safari17_0, and firefox133 all get
a clean 200 (WooCommerce Store API and full HTML alike). chrome131 also
403s. Pin chrome124, matching the cassandraonlinemarket_ht pattern.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class SupasaveBnSpider(WooBaseSpider):
    name = "supasave_bn"
    allowed_domains = ["seria.supasave.com.bn"]
    currency = "BND"
    language = "en"
    BASE_URL = "https://seria.supasave.com.bn/wp-json/wc/store/v1/products"

    # chrome120 (the repo-wide pinned profile) and chrome131 403 on this
    # tenant; chrome124/safari17_0/firefox133 clear it (confirmed live
    # 2026-09-06). Disable the random-profile middleware and pin chrome124,
    # matching its User-Agent header so the TLS handshake and header
    # fingerprint agree (curl_cffi forwards Scrapy's headers verbatim).
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

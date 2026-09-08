"""
Mohasbeza (Addis Ababa, Ethiopia) — https://mohasbeza.com/.

WooCommerce (Woostify theme) with the standard versioned Store API, no auth.
Grocery-dominant catalogue (pantry & food staples, spices/herbs, food oils,
flour, rice, oats, butter, milk, coffee, tea, tuna, pasta, sugar) plus a small
cleaning/packaging tail. ETB at currency_minor_unit=2.

TLS trap: the Cloudflare edge on this tenant 403s EVERY Chrome and Safari
curl_cffi profile tried (chrome120/124/131, safari17_0) and clears on
firefox133 — the opposite direction from the usual "chrome124 recovers it"
case, so the repo-pinned chrome120 profile has to be overridden here. The
override needs all three parts: disable RandomBrowserMiddleware (it rewrites
meta["impersonate"] per request), set a matching Firefox User-Agent (curl_cffi
forwards Scrapy's headers verbatim, and a Firefox handshake under a Chrome UA
is itself a 403 tell), and set IMPERSONATE_PROFILE for the handler.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class MohasbezaEtSpider(WooBaseSpider):
    name = "mohasbeza_et"
    allowed_domains = ["mohasbeza.com", "www.mohasbeza.com"]
    currency = "ETB"
    language = "en"
    BASE_URL = "https://mohasbeza.com/wp-json/wc/store/v1/products"

    custom_settings = {
        **WooBaseSpider.custom_settings,
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) "
            "Gecko/20100101 Firefox/133.0"
        ),
    }
    IMPERSONATE_PROFILE = "firefox133"

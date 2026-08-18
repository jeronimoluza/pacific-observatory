"""
e-Tohfa (Afghanistan) — https://www.e-tohfa.com/.

General marketplace (gifts, electronics, fashion). The site's WAF blocks the
project-wide scrapy_impersonate chrome120 TLS fingerprint outright (curl_cffi
impersonate="chrome120" -> 403, independent of the declared UA header) and
also blocks the literal "Chrome/120.0.0.0" UA string that CustomUserAgent-
Middleware randomly rotates in (3 of its 5 UAs use Chrome/120). This
subclass disables both middlewares, re-enables the stock scrapy
UserAgentMiddleware, and pins a newer Chrome UA via settings.USER_AGENT,
which passes consistently. Bare domain 301s to www but drops the
/wp-json/ path, so we hit www directly. API's currency_code is USD (site
prices in USD despite serving Kabul, Afghanistan, per its contact page).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class EtohfaAfSpider(WooBaseSpider):
    name = "etohfa_af"
    allowed_domains = ["www.e-tohfa.com"]
    currency = "USD"
    language = "en"
    BASE_URL = "https://www.e-tohfa.com/wp-json/wc/store/v1/products"

    custom_settings = {
        **WooBaseSpider.custom_settings,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": 500,
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
            "scrapy.downloadermiddlewares.retry.RetryMiddleware": 590,
            "scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware": 750,
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
    }

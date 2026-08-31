"""Spider for Guishop (Guinea) -- https://gui-shop.com/.

Standard WooCommerce Store API on the versioned route. Phones/electronics
catalog (Samsung, iPhone, Redmi), ~57 products, GNF at currency_minor_unit=0
(no scaling needed).

WAF TRAP: the site's Store API 403s the project's default impersonated
TLS fingerprint (chrome120 -- confirmed via curl_cffi directly) but passes
chrome124 cleanly. Pinned IMPERSONATE_BROWSERS accordingly.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class GuishopGnSpider(WooBaseSpider):
    name = "guishop_gn"
    allowed_domains = ["gui-shop.com"]
    currency = "GNF"
    language = "fr"
    BASE_URL = "https://gui-shop.com/wp-json/wc/store/v1/products"
    custom_settings = {
        **WooBaseSpider.custom_settings,
        "IMPERSONATE_BROWSERS": ["chrome124"],
        "RETRY_HTTP_CODES": [403, 500, 502, 503, 504, 408, 429],
        "RETRY_TIMES": 8,
    }

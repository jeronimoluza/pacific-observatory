"""Djibouti Fresh (Djibouti) — https://www.djiboutifresh.com. WooCommerce Store API.

WooCommerce Store API v1, unauthenticated. 100+ products, 84 of the first 100 priced
(probed 2026-09-11). prices.currency_code=DJF, currency_minor_unit=0 -- franc has no
subunit, no division applied.

Full-range online grocer: Epicerie, Lait, Boucherie, Fruits, Legumes, Traiteur, plus
Sante/Beaute and Articles Bebe.

GOTCHA -- the humans_21909 cookie handshake. The origin intermittently answers ANY path
(the Store API included) with an 83-byte HTTP 409 whose whole body is

    <script>document.cookie = "humans_21909=1"; document.location.reload(true)</script>

This is the same humans.txt-style handshake recorded for eshopuganda.com in
references/known_blockers.md -- NOT a WAF and not rate limiting. It is intermittent: the
first collection run of 2026-09-11 returned 84 rows and the next one five minutes later
got a single 409 and zero rows. Sending the cookie unconditionally clears it
(verified: 409/83 bytes without, 200/56KB with), so it is set on every request below.
If this source ever reports zero rows again, check for a NEW cookie name in the stub
before assuming the site is down.

Page family parsed: API (/wp-json/wc/store/v1/products).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class DjiboutifreshDjSpider(WooBaseSpider):
    name = "djiboutifresh_dj"
    allowed_domains = ["djiboutifresh.com"]
    currency = "DJF"
    language = "fr"
    BASE_URL = "https://www.djiboutifresh.com/wp-json/wc/store/v1/products"

    # See the humans_21909 note in the module docstring.
    custom_settings = {
        **WooBaseSpider.custom_settings,
        # Scrapy's CookiesMiddleware drops a hand-set Cookie header, so turn it
        # off for this spider and let the header through verbatim.
        "COOKIES_ENABLED": False,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json",
            "Cookie": "humans_21909=1",
        },
    }

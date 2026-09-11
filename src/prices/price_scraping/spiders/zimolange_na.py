"""
Zimolange -- https://zimolange.com/ (Korean skincare and beauty retailer,
Namibia).

Standard WooCommerce Store API at /wp-json/wc/store/v1/products. NAD
prices at currency_minor_unit=2 (e.g. raw "48500" -> N$485.00), confirmed
against the site's own price_html on the same row.

Cloudflare fingerprints the TLS profile: the repo-wide default
`chrome120` impersonate profile 403s (confirmed on a8, 2026-09-11), while
`chrome124` and `safari17_0` both clear with 200. Pin `chrome124`.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class ZimolangeNaSpider(WooBaseSpider):
    name = "zimolange_na"
    allowed_domains = ["zimolange.com"]
    currency = "NAD"
    language = "en"
    BASE_URL = "https://zimolange.com/wp-json/wc/store/v1/products"
    IMPERSONATE_PROFILE = "chrome124"

"""
Farm Fresh (The Gambia) — https://farmfresh.gm/.

Standard WooCommerce Store API on the versioned route, no auth. Narrow
fresh-food catalogue (meat, poultry & eggs, vegetables, fruit, spices,
cereals, natural oils) with GMD prices at currency_minor_unit=2.

The origin is a slow shared cPanel host: first-byte latency runs 20-40s and
occasionally longer. The repo-wide DOWNLOAD_TIMEOUT of 15s (settings.py) times
out every request here and the spider reports a clean zero — so the timeout is
raised for this source only. Nothing else about the site needs special
handling.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class FarmfreshGmSpider(WooBaseSpider):
    name = "farmfresh_gm"
    allowed_domains = ["farmfresh.gm"]
    currency = "GMD"
    language = "en"
    BASE_URL = "https://farmfresh.gm/wp-json/wc/store/v1/products"

    custom_settings = {
        **WooBaseSpider.custom_settings,
        "DOWNLOAD_TIMEOUT": 120,
    }

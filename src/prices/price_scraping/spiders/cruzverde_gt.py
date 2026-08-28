"""
Cruz Verde (Guatemala) — https://cruzverde.com.gt/.

Pharmacy retailer; category taxonomy is brand names, not product types, so
the whole catalog is walked unfiltered.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class CruzverdeGtSpider(WooBaseSpider):
    name = "cruzverde_gt"
    allowed_domains = ["cruzverde.com.gt"]
    currency = "GTQ"
    language = "es"
    BASE_URL = "https://cruzverde.com.gt/wp-json/wc/store/v1/products"

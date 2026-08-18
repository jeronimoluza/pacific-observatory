"""
A Pharma Solutions (Lebanon) — https://apharmasolutions.com/.

Medical-supplies distributor (ampoules, IV sets, intravenous solutions).
Contact page lists a Nabi Ayla, Lebanon address and a +961 phone number;
prices in USD (common for Lebanese online retail given LBP instability).

5 IV-solution SKUs (ids 279-283) carry price=0 upstream -- confirmed live
2026-08-17 via the Store API (prices.price="0", price_html="") that these
are genuine get-a-quote listings with no fixed price set, not a parse
failure. Dropped at the spider rather than emitted as a 0-price row.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class ApharmasolutionsLbSpider(WooBaseSpider):
    name = "apharmasolutions_lb"
    allowed_domains = ["apharmasolutions.com"]
    currency = "USD"
    language = "en"
    BASE_URL = "https://apharmasolutions.com/wp-json/wc/store/v1/products"

    def _item(self, p: dict):
        item = super()._item(p)
        if item and float(item["price"]) <= 0:
            return None
        return item

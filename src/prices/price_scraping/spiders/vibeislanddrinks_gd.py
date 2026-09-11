"""
Vibe Island Drinks (Grenada) -- https://vibeislanddrinks.com/.

Standard WooCommerce Store API. XCD prices at currency_minor_unit=2
(e.g. price "18000" -> $180.00), currency_code confirmed as "XCD" directly
from the Store API response.

Small catalog by design (specialty beverage brand, not a general grocer):
the Store API returns exactly 5 SKUs total (per_page=50 page 1 -> 5 rows,
page 2 -> 0 rows/empty). Per the campaign brief, a small catalog that is
genuinely the whole site is not a rejection reason -- only a catalog that
fails to paginate is. Kept for breadth (beverages COICOP division).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class VibeislanddrinksGdSpider(WooBaseSpider):
    name = "vibeislanddrinks_gd"
    allowed_domains = ["vibeislanddrinks.com"]
    currency = "XCD"
    language = "en"
    BASE_URL = "https://vibeislanddrinks.com/wp-json/wc/store/v1/products"

"""
Horizons Supplies (Antigua and Barbuda) — https://www.horizonssupplies.com/.

Standard WooCommerce Store API on the versioned route. Wide wholesale
food-service catalog (meat, seafood, produce, bakery, dairy, beverages,
liquor, hotel/restaurant supplies) with XCD prices at
currency_minor_unit=2. Self-described "Antigua's #1 Food & Beverage
Supplier"; warehouse at St. Pauls, Mamora Bay, Antigua (PO Box 63,
St. Johns, Antigua) -- confirmed via /contact-us/.

Page 1 of the unfiltered walk (default WooCommerce ordering, oldest
post_id first) is dominated by draft/import artifacts: 71 of 100 rows
named literally "Product", slug "product-<n>", price 0. Verified against
the live API that these are confined to page 1 -- pages 2, 3, 5, 10 and
20 returned 0/100 such rows. They are dropped in _item rather than left
to the classifier.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class HorizonssuppliesAgSpider(WooBaseSpider):
    name = "horizonssupplies_ag"
    allowed_domains = ["horizonssupplies.com"]
    currency = "XCD"
    language = "en"
    BASE_URL = "https://www.horizonssupplies.com/wp-json/wc/store/v1/products"

    def _item(self, p: dict):
        item = super()._item(p)
        if item is None:
            return None
        # Store-setup placeholders: unnamed and unpriced. Both conditions
        # required so a real product that is merely out of price never drops.
        if item["product_name"].strip().lower() == "product" and (
            item["price"] in ("0", "0.0", "0.00")
        ):
            return None
        return item

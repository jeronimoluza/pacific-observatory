"""
Spider for Cost-U-Less St. Maarten — https://www.costuless.com/st-maarten.

NCR Freshop tenant app_key=cost_u_less, store_id=1966 (1,704 items,
distinct catalog from the other three Cost-U-Less territory stores under
this app_key — verified live: differing totals and SKUs per store_id).

Currency correction: the shard recorded USD (assumed, since the payload
has no currency_code field), but this store's price display string
consistently uses "ƒ" (e.g. "ƒ5,99") — the guilder/florin symbol, not "$".
That is live evidence this store prices in ANG, matching
src/configs/countries.yaml's ANG for sint_maarten_dutch_part, not the
shard's USD assumption.
"""

from price_scraping.spiders._freshop_base import FreshopBaseSpider


class CostulessSxSpider(FreshopBaseSpider):
    name = "costuless_sx"
    currency = "ANG"
    language = "en"

    APP_KEY = "cost_u_less"
    STORE_ID = "1966"

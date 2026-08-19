"""
Spider for Cost-U-Less Grand Cayman — https://www.costuless.com/grand-cayman.

NCR Freshop tenant app_key=cost_u_less, store_id=3821 (1,574 items,
distinct catalog from the other three Cost-U-Less territory stores under
this app_key — verified live: differing totals and SKUs per store_id, not
one catalog duplicated across countries).

Currency caveat: the product payload has no currency_code field. The
price display string here is plain "$" (e.g. "$ 2.49"), which is ambiguous
between USD and KYD (Cayman's own $ symbol) — Cayman is USD-pegged and
this is a US warehouse chain, so USD is the working assumption, unconfirmed
from the API alone.
"""

from price_scraping.spiders._freshop_base import FreshopBaseSpider


class CostulessKySpider(FreshopBaseSpider):
    name = "costuless_ky"
    currency = "USD"
    language = "en"

    APP_KEY = "cost_u_less"
    STORE_ID = "3821"

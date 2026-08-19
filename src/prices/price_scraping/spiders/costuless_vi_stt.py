"""
Spider for Cost-U-Less St. Thomas (US Virgin Islands) —
https://www.costuless.com/st-thomas.

NCR Freshop tenant app_key=cost_u_less, store_id=1967 (2,219 items,
distinct catalog from the other three Cost-U-Less territory stores under
this app_key). USVI is USD natively, so this is the one Cost-U-Less
territory where the currency assumption is solid (price strings are plain
"$", e.g. "$5.29").
"""

from price_scraping.spiders._freshop_base import FreshopBaseSpider


class CostulessViSttSpider(FreshopBaseSpider):
    name = "costuless_vi_stt"
    currency = "USD"
    language = "en"

    APP_KEY = "cost_u_less"
    STORE_ID = "1967"

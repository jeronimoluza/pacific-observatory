"""
Spider for Cost-U-Less St. Croix (US Virgin Islands) —
https://www.costuless.com/.

NCR Freshop tenant app_key=cost_u_less, store_id=1965 (2,085 items,
distinct catalog from the other three Cost-U-Less territory stores under
this app_key — same tenant/country as St. Thomas (costuless_vi_stt), but a
separate physical store with likely-high-but-not-identical SKU overlap).
USVI is USD natively, so the currency assumption is solid here (price
strings are plain "$", e.g. "$10.98").
"""

from price_scraping.spiders._freshop_base import FreshopBaseSpider


class CostulessViStxSpider(FreshopBaseSpider):
    name = "costuless_vi_stx"
    currency = "USD"
    language = "en"

    APP_KEY = "cost_u_less"
    STORE_ID = "1965"

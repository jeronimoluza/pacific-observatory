"""Cash N' Carry Chuuk food category."""

from __future__ import annotations

from ._woo_base import WooBaseSpider


class CashNCarryFmSpider(WooBaseSpider):
    name = "cashncarry_fm"
    allowed_domains = ["cnc.fm"]
    currency = "USD"
    language = "en"
    BASE_URL = "https://cnc.fm/wp-json/wc/store/v1/products"
    CATEGORY_ID = 92

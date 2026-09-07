"""Na2ox Trading PNG take.app grocery/convenience storefront."""

from __future__ import annotations

from ._takeapp_flight_base import TakeAppFlightSpider


class Na2oxTradingPgSpider(TakeAppFlightSpider):
    name = "na2ox_trading_pg"
    currency = "PGK"
    language = "en"
    STORE_ALIAS = "na2oxtrading"
    COUNTRY_CODE = "PG"

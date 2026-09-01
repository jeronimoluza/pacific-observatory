"""Bula Banquet Fiji take.app prepared-food storefront."""

from __future__ import annotations

from ._takeapp_flight_base import TakeAppFlightSpider


class BulaBanquetFjSpider(TakeAppFlightSpider):
    name = "bula_banquet_fj"
    currency = "FJD"
    language = "en"
    STORE_ALIAS = "bulabanquet"
    COUNTRY_CODE = "FJ"

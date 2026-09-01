"""SamoaEats take.app prepared-food storefront."""

from __future__ import annotations

from ._takeapp_flight_base import TakeAppFlightSpider


class SamoaEatsWsSpider(TakeAppFlightSpider):
    name = "samoa_eats_ws"
    currency = "WST"
    language = "en"
    STORE_ALIAS = "samoaeats"
    COUNTRY_CODE = "WS"

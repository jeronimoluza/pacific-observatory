"""ORENJBLAK Vanuatu TakeApp storefront."""

from price_scraping.spiders._takeapp_flight_base import TakeAppFlightSpider


class OrenjblakVuSpider(TakeAppFlightSpider):
    name = "orenjblak_vu"
    STORE_ALIAS = "orenjblak"
    COUNTRY_CODE = "VU"
    currency = "VUV"
    language = "en"
    PRICE_DIVISOR = 1

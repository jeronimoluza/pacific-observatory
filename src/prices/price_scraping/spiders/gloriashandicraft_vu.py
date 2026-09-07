"""Gloria's Handicraft Vanuatu TakeApp storefront."""

from price_scraping.spiders._takeapp_flight_base import TakeAppFlightSpider


class GloriasHandicraftVuSpider(TakeAppFlightSpider):
    name = "gloriashandicraft_vu"
    STORE_ALIAS = "gloriashandicraft"
    COUNTRY_CODE = "VU"
    currency = "VUV"
    language = "en"
    PRICE_DIVISOR = 1

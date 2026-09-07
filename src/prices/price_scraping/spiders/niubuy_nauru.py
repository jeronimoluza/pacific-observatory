"""NiuBuy Nauru TakeApp storefront."""

from price_scraping.spiders._takeapp_flight_base import TakeAppFlightSpider


class NiuBuyNauruSpider(TakeAppFlightSpider):
    name = "niubuy_nauru"
    STORE_ALIAS = "niubuystorelink"
    COUNTRY_CODE = "NR"
    currency = "AUD"
    language = "en"


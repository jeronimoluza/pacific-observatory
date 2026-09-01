from price_scraping.spiders._wolt_base import WoltBaseSpider


class KSupermarketWoltFiSpider(WoltBaseSpider):
    name = "k_supermarket_wolt_fi"
    currency = "EUR"
    language = "fi"
    VENUE_PATH = "en/fin/helsinki"
    VENUE_SLUG = "k-supermarket-mustapekka"

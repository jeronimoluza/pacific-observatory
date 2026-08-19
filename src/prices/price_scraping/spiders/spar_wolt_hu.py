from price_scraping.spiders._wolt_base import WoltBaseSpider


class SparWoltHuSpider(WoltBaseSpider):
    name = "spar_wolt_hu"
    currency = "HUF"
    language = "hu"
    VENUE_PATH = "en/hun/budapest"
    VENUE_SLUG = "sparszupermarket-klauzalter"

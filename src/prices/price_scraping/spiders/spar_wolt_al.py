from price_scraping.spiders._wolt_base import WoltBaseSpider


class SparWoltAlSpider(WoltBaseSpider):
    name = "spar_wolt_al"
    currency = "ALL"
    language = "sq"
    VENUE_PATH = "en/alb/tirana"
    VENUE_SLUG = "spar-mine-peza"

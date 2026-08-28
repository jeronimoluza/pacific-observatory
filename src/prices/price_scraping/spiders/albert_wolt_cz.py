from price_scraping.spiders._wolt_base import WoltBaseSpider


class AlbertWoltCzSpider(WoltBaseSpider):
    name = "albert_wolt_cz"
    currency = "CZK"
    language = "cs"
    VENUE_PATH = "en/cze/prague"
    VENUE_SLUG = "albert-sokolovska"

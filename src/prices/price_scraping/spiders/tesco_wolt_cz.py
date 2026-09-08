from price_scraping.spiders._wolt_base import WoltBaseSpider


class TescoWoltCzSpider(WoltBaseSpider):
    name = "tesco_wolt_cz"
    currency = "CZK"
    language = "cs"
    VENUE_PATH = "en/cze/prague"
    VENUE_SLUG = "tesco-hypermarket-narodni"

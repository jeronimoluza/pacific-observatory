from price_scraping.spiders._wolt_base import WoltBaseSpider


class BravoWoltAzSpider(WoltBaseSpider):
    name = "bravo_wolt_az"
    currency = "AZN"
    language = "az"
    VENUE_PATH = "en/aze/baku"
    VENUE_SLUG = "bravo-supermarket-azure"

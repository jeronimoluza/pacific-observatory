from price_scraping.spiders._wolt_base import WoltBaseSpider


class FarmaciAgWoltAlSpider(WoltBaseSpider):
    name = "farmaci_ag_wolt_al"
    currency = "ALL"
    language = "sq"
    VENUE_PATH = "en/alb/tirana"
    VENUE_SLUG = "farmaci-ag"

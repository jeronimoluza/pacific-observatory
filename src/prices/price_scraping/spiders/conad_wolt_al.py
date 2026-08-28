from price_scraping.spiders._wolt_base import WoltBaseSpider


class ConadWoltAlSpider(WoltBaseSpider):
    name = "conad_wolt_al"
    currency = "ALL"
    language = "sq"
    VENUE_PATH = "en/alb/tirana"
    VENUE_SLUG = "conad-albania-bulevardi-zogu-i"

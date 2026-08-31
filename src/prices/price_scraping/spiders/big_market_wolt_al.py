from price_scraping.spiders._wolt_base import WoltBaseSpider


class BigMarketWoltAlSpider(WoltBaseSpider):
    name = "big_market_wolt_al"
    currency = "ALL"
    language = "sq"
    VENUE_PATH = "en/alb/tirana"
    VENUE_SLUG = "big-market-garden"

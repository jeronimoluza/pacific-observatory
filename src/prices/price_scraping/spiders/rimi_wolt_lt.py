from price_scraping.spiders._wolt_base import WoltBaseSpider


class RimiWoltLtSpider(WoltBaseSpider):
    name = "rimi_wolt_lt"
    currency = "EUR"
    language = "lt"
    VENUE_PATH = "en/ltu/vilnius"
    VENUE_SLUG = "rimi-mylia"

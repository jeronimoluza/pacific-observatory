from price_scraping.spiders._wolt_base import WoltBaseSpider


class SmallWoltKzSpider(WoltBaseSpider):
    name = "small_wolt_kz"
    currency = "KZT"
    language = "ru"
    VENUE_PATH = "en/kaz/almaty"
    VENUE_SLUG = "small-tole-bi"

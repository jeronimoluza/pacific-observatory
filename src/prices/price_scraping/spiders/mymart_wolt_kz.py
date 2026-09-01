from price_scraping.spiders._wolt_base import WoltBaseSpider


class MymartWoltKzSpider(WoltBaseSpider):
    name = "mymart_wolt_kz"
    currency = "KZT"
    language = "ru"
    VENUE_PATH = "en/kaz/almaty"
    VENUE_SLUG = "my-mart-lumiere"

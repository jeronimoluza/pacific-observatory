from price_scraping.spiders._wolt_base import WoltBaseSpider


class TescoWoltSkSpider(WoltBaseSpider):
    name = "tesco_wolt_sk"
    currency = "EUR"
    language = "sk"
    VENUE_PATH = "en/svk/bratislava"
    VENUE_SLUG = "tesco-hypermarket-zlate-piesky"

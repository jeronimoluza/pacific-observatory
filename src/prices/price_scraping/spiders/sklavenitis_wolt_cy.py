from price_scraping.spiders._wolt_base import WoltBaseSpider


class SklavenitisWoltCySpider(WoltBaseSpider):
    name = "sklavenitis_wolt_cy"
    currency = "EUR"
    language = "el"
    VENUE_PATH = "en/cyp/nicosia"
    VENUE_SLUG = "sklavenitis-engomi"

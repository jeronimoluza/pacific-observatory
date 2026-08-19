from price_scraping.spiders._wolt_base import WoltBaseSpider


class LanoiWoltMkSpider(WoltBaseSpider):
    name = "lanoi_wolt_mk"
    currency = "MKD"
    language = "mk"
    VENUE_PATH = "en/mkd/skopje"
    VENUE_SLUG = "la-noi-shop"

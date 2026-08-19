from price_scraping.spiders._wolt_base import WoltBaseSpider


class CarrefourWoltGeSpider(WoltBaseSpider):
    name = "carrefour_wolt_ge"
    currency = "GEL"
    language = "ka"
    VENUE_PATH = "en/geo/tbilisi"
    VENUE_SLUG = "carrefour-vekua"

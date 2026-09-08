from price_scraping.spiders._wolt_base import WoltBaseSpider


class TobaccoLuxWoltMkSpider(WoltBaseSpider):
    name = "tobacco_lux_wolt_mk"
    currency = "MKD"
    language = "mk"
    VENUE_PATH = "en/mkd/skopje"
    VENUE_SLUG = "tobacco-lux"

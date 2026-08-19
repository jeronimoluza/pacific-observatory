from price_scraping.spiders._wolt_base import WoltBaseSpider


class AbVassilopoulosWoltGrSpider(WoltBaseSpider):
    name = "ab_vassilopoulos_wolt_gr"
    currency = "EUR"
    language = "el"
    VENUE_PATH = "en/grc/athens"
    VENUE_SLUG = "ab-vassilopoulos-mets"

from price_scraping.spiders._wolt_base import WoltBaseSpider


class ReptilMarketWoltMkSpider(WoltBaseSpider):
    name = "reptil_market_wolt_mk"
    currency = "MKD"
    language = "mk"
    VENUE_PATH = "en/mkd/skopje"
    VENUE_SLUG = "reptil-market-karposh-4"

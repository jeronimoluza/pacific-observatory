from price_scraping.spiders._wolt_base import WoltBaseSpider


class MaxiWoltRsSpider(WoltBaseSpider):
    name = "maxi_wolt_rs"
    currency = "RSD"
    language = "sr"
    VENUE_PATH = "en/srb/belgrade"
    VENUE_SLUG = "maxi-bulevar-osloboenja"

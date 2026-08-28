"""Spider for Diarle (Senegal) -- https://diarle.sn/."""

from price_scraping.spiders._prestashop_base import PrestashopBaseSpider


class DiarleSpider(PrestashopBaseSpider):
    name = "diarle"
    allowed_domains = ["diarle.sn"]
    currency = "XOF"
    language = "fr"
    HOME_URL = "https://diarle.sn/fr/"

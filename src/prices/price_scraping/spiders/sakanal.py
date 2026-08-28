"""Spider for Sakanal (Senegal) -- https://sakanal.sn/."""

from price_scraping.spiders._prestashop_base import PrestashopBaseSpider


class SakanalSpider(PrestashopBaseSpider):
    name = "sakanal"
    allowed_domains = ["sakanal.sn"]
    currency = "XOF"
    language = "fr"
    HOME_URL = "https://sakanal.sn/fr/"

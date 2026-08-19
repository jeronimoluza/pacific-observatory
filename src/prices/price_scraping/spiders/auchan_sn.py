"""Spider for Auchan Senegal -- https://www.auchan.sn/."""

from price_scraping.spiders._prestashop_base import PrestashopBaseSpider


class AuchanSnSpider(PrestashopBaseSpider):
    name = "auchan_sn"
    allowed_domains = ["auchan.sn"]
    currency = "XOF"
    language = "fr"
    HOME_URL = "https://www.auchan.sn/"

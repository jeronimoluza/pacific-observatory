"""Jumbo Colombia -- https://www.jumbocolombia.com/. Cencosud CO flagship hypermarket, full-line."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class JumboCoSpider(VtexBaseSpider):
    name = "jumbo_co"
    allowed_domains = ["jumbocolombia.com"]
    HOST = "www.jumbocolombia.com"
    currency = "COP"
    language = "es"

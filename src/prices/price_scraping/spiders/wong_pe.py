"""Wong (Peru) -- https://www.wong.pe/. Premium/upper-mid Cencosud banner, VTEX."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class WongPeSpider(VtexBaseSpider):
    name = "wong_pe"
    allowed_domains = ["wong.pe"]
    HOST = "www.wong.pe"
    currency = "PEN"
    language = "es"

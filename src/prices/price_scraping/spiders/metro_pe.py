"""Metro Peru -- https://www.metro.pe/. Cencosud discount banner, VTEX. Full-line supermarket."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class MetroPeSpider(VtexBaseSpider):
    name = "metro_pe"
    allowed_domains = ["metro.pe"]
    HOST = "www.metro.pe"
    currency = "PEN"
    language = "es"

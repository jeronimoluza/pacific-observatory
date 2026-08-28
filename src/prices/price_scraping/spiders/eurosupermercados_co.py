"""Euro Supermercados (Colombia) -- https://www.eurosupermercados.com.co/. Mid-tier Colombian grocery chain with home delivery."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class EurosupermercadosCoSpider(VtexBaseSpider):
    name = "eurosupermercados_co"
    allowed_domains = ["eurosupermercados.com.co"]
    HOST = "www.eurosupermercados.com.co"
    currency = "COP"
    language = "es"

"""plazaVea (Peru) -- https://www.plazavea.com.pe/supermercado. Intercorp mass-market chain, VTEX. No sc= sales-channel param needed -- category-scoped queries (fq=C:/.../) returned products with or without sc=1."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class PlazaveaPeSpider(VtexBaseSpider):
    name = "plazavea_pe"
    allowed_domains = ["plazavea.com.pe"]
    HOST = "www.plazavea.com.pe"
    currency = "PEN"
    language = "es"

"""Jumbo Argentina -- https://www.jumbo.com.ar/. Cencosud AR flagship hypermarket, full-line incl. fresh produce/meat. Same VTEX tenant/account family as Disco AR and Vea AR."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class JumboArSpider(VtexBaseSpider):
    name = "jumbo_ar"
    allowed_domains = ["jumbo.com.ar"]
    HOST = "www.jumbo.com.ar"
    currency = "ARS"
    language = "es"

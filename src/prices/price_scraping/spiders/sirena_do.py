"""Sirena / Sirena Go (Dominican Republic) -- https://www.sirena.do/. VTEX tenant, whole-catalog crawl."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class SirenaDoSpider(VtexBaseSpider):
    name = "sirena_do"
    allowed_domains = ["sirena.do"]
    HOST = "www.sirena.do"
    currency = "DOP"
    language = "es"

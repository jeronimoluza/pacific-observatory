"""El Dorado (Uruguay) -- https://www.eldorado.com.uy/. Full-line Uruguayan chain, fresh produce confirmed (banana)."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class EldoradoUySpider(VtexBaseSpider):
    name = "eldorado_uy"
    allowed_domains = ["eldorado.com.uy"]
    HOST = "www.eldorado.com.uy"
    currency = "UYU"
    language = "es"

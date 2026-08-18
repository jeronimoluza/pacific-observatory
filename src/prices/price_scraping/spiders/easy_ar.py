"""Easy Argentina -- https://www.easy.com.ar/. Home-improvement hypermarket, independent VTEX tenant from the Cencosud AR banners."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class EasyArSpider(VtexBaseSpider):
    name = "easy_ar"
    allowed_domains = ["easy.com.ar"]
    HOST = "www.easy.com.ar"
    currency = "ARS"
    language = "es"

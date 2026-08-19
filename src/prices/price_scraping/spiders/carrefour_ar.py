"""Carrefour Argentina -- https://www.carrefour.com.ar/. Full-line hypermarket, independent VTEX tenant from the Cencosud AR banners."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class CarrefourArSpider(VtexBaseSpider):
    name = "carrefour_ar"
    allowed_domains = ["carrefour.com.ar"]
    HOST = "www.carrefour.com.ar"
    currency = "ARS"
    language = "es"

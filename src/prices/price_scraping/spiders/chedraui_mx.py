"""Chedraui (Mexico) -- https://www.chedraui.com.mx/. Full-line supermarket incl. fresh produce (Frutas y Verduras dept confirmed)."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class ChedrauiMxSpider(VtexBaseSpider):
    name = "chedraui_mx"
    allowed_domains = ["chedraui.com.mx"]
    HOST = "www.chedraui.com.mx"
    currency = "MXN"
    language = "es"

"""Paiz (Guatemala) -- https://www.paiz.com.gt/. Walmart Centroamerica banner, full-line incl. meat."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class PaizGtSpider(VtexBaseSpider):
    name = "paiz_gt"
    allowed_domains = ["paiz.com.gt"]
    HOST = "www.paiz.com.gt"
    currency = "GTQ"
    language = "es"

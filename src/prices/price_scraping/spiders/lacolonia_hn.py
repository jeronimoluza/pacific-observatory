"""Supermercados La Colonia (Honduras) -- https://www.lacolonia.com/. VTEX tenant, whole-catalog crawl."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class LacoloniaHnSpider(VtexBaseSpider):
    name = "lacolonia_hn"
    allowed_domains = ["lacolonia.com"]
    HOST = "www.lacolonia.com"
    currency = "HNL"
    language = "es"

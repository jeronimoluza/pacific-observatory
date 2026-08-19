"""Spider for gtPlaza (Guyana) -- https://gtplaza.com/. CSV listed the
platform as Custom; re-verification found itemprop-tagged PrestaShop
category HTML (/{id}-{slug}), so it is scaffolded on the shared PrestaShop
base."""

from price_scraping.spiders._prestashop_base import PrestashopBaseSpider


class GtplazaSpider(PrestashopBaseSpider):
    name = "gtplaza"
    allowed_domains = ["gtplaza.com"]
    currency = "GYD"
    language = "en"
    HOME_URL = "https://gtplaza.com/"

"""Farmacia Guerrero (Andorra) -- https://www.farmacia-guerrero.com/en/.

Andorran pharmacy (AD500 / +376 contact details on the storefront). OpenCart
with clean-SEO URLs; the home-page menu is walked by the shared
`_opencart_seo_base.py`, cards are parsed by the stock `OpencartBaseSpider`.
"""

from price_scraping.spiders._opencart_seo_base import OpencartSeoWalkSpider


class FarmaciaguerreroAdSpider(OpencartSeoWalkSpider):
    name = "farmaciaguerrero_ad"
    allowed_domains = ["farmacia-guerrero.com"]
    currency = "EUR"
    language = "en"
    NAV_URL = "https://www.farmacia-guerrero.com/en/"
    LANG_PREFIX = "/en"

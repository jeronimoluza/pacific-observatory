"""Farmacia Meritxell (Andorra) -- https://www.farmaciameritxell.com/.

Andorran pharmacy (AD500 / +376 contact details on the storefront). OpenCart
with clean-SEO URLs; the home-page menu is walked by the shared
`_opencart_seo_base.py`, cards are parsed by the stock `OpencartBaseSpider`.
"""

from price_scraping.spiders._opencart_seo_base import OpencartSeoWalkSpider


class FarmaciameritxellAdSpider(OpencartSeoWalkSpider):
    name = "farmaciameritxell_ad"
    allowed_domains = ["farmaciameritxell.com"]
    currency = "EUR"
    language = "es"
    NAV_URL = "https://www.farmaciameritxell.com/"
    LANG_PREFIX = ""

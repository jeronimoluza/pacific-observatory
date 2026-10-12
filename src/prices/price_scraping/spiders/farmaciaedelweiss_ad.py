"""Farmacia Edelweiss (Andorra) -- https://farmaciaedelweiss.com/.

Andorran pharmacy (AD500 / +376 contact details on the storefront). OpenCart
with clean-SEO URLs; the home-page menu is walked by the shared
`_opencart_seo_base.py`, cards are parsed by the stock `OpencartBaseSpider`.
"""

from price_scraping.spiders._opencart_seo_base import OpencartSeoWalkSpider


class FarmaciaedelweissAdSpider(OpencartSeoWalkSpider):
    name = "farmaciaedelweiss_ad"
    allowed_domains = ["farmaciaedelweiss.com"]
    currency = "EUR"
    language = "es"
    NAV_URL = "https://farmaciaedelweiss.com/"
    LANG_PREFIX = ""

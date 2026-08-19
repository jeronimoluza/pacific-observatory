"""Santa Isabel (Chile) -- https://www.santaisabel.cl/. Cencosud banner, VTEX behind
a custom storefront that 404s the catalog API on the retail domain; the underlying
`*.myvtex.com` origin serves the catalog directly."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class SantaIsabelClSpider(VtexBaseSpider):
    name = "santaisabel_cl"
    allowed_domains = ["myvtex.com"]
    HOST = "santaisabel.myvtex.com"
    currency = "CLP"
    language = "es"

"""Jumbo (Chile) -- https://www.jumbo.cl/. Cencosud banner, VTEX behind a custom
Next.js storefront that 404s the catalog API on the retail domain; the underlying
`*.myvtex.com` origin serves the catalog directly."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class JumboClSpider(VtexBaseSpider):
    name = "jumbo_cl"
    allowed_domains = ["myvtex.com"]
    HOST = "jumbocl.myvtex.com"
    currency = "CLP"
    language = "es"

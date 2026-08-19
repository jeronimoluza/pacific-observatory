"""Vivanda (Peru) -- https://www.vivanda.com.pe/. Premium Cencosud banner, VTEX behind
a custom storefront that hides the catalog API on the retail domain; the underlying
`vivanda.myvtex.com` origin serves the catalog directly. Prior rounds claimed it had
migrated off VTEX -- it has not."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class VivandaPeSpider(VtexBaseSpider):
    name = "vivanda_pe"
    allowed_domains = ["myvtex.com"]
    HOST = "vivanda.myvtex.com"
    currency = "PEN"
    language = "es"

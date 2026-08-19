"""Ta-Ta (Uruguay) -- https://www.tata.com.uy/. Full-line VTEX chain.

Custom domain 404s on /api/catalog_system/pub/... (Gatsby front-end only);
the tenant's myvtex.com origin serves the catalog directly (VTEX origin
bypass), account slug "tatauy".
"""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class TataUySpider(VtexBaseSpider):
    name = "tata_uy"
    allowed_domains = ["tatauy.myvtex.com"]
    HOST = "tatauy.myvtex.com"
    currency = "UYU"
    language = "es"

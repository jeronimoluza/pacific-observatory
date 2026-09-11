"""
Hemkop (Sweden) -- https://www.hemkop.se/.

Axfood-group SAP Commerce Cloud storefront. Sibling of Willys (willys_se);
both run the identical axfood/rest/v1/c/<category> catalog API, confirmed
live 2026-09-10 -- see _axfood_base.py. Preferred over the tenant's
_next/data/<buildId>/... route (buildId rotates on every deploy) because
the REST tree needs no buildId and is the same stable shape shared with
Willys.
"""

from price_scraping.spiders._axfood_base import AxfoodBaseSpider


class HemkopSeSpider(AxfoodBaseSpider):
    name = "hemkop_se"
    allowed_domains = ["www.hemkop.se"]
    DOMAIN = "www.hemkop.se"
    currency = "SEK"
    language = "sv"

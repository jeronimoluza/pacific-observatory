"""
Willys (Sweden) -- https://www.willys.se/.

Axfood-group SAP Commerce Cloud storefront. Sibling of Hemkop (hemkop_se);
both run the identical axfood/rest/v1/c/<category> catalog API, confirmed
live 2026-09-10 -- see _axfood_base.py for the pagination + sitemap
discovery mechanism. SEK, priceValue already decimal (no minor-unit
scaling).
"""

from price_scraping.spiders._axfood_base import AxfoodBaseSpider


class WillysSeSpider(AxfoodBaseSpider):
    name = "willys_se"
    allowed_domains = ["www.willys.se"]
    DOMAIN = "www.willys.se"
    currency = "SEK"
    language = "sv"

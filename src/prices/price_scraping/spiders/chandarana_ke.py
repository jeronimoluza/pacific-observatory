"""
Spider for Chandarana Foodplus (Kenya) — https://foodplus.co.ke/.

The CSV's domain (chandaranafoodplus.com) is NXDOMAIN; the real domain
foodplus.co.ke is Magento with an unauthenticated REST /rest/V1/products
surface (18,000+ products, 19,471 by /rest/V1/categories' root count) —
unusual, most Magento REST product endpoints need a bearer token, but this
one is open.
"""

from price_scraping.spiders._magento_base import MagentoRestBaseSpider


class ChandaranaKeSpider(MagentoRestBaseSpider):
    name = "chandarana_ke"
    allowed_domains = ["foodplus.co.ke"]
    currency = "KES"
    language = "en"

    BASE_URL = "https://foodplus.co.ke"

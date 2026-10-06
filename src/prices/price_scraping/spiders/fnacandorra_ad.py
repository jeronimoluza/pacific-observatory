"""Fnac Andorra -- https://fnac-andorra.com/.

Andorran Fnac storefront (electronics, computing, books, games; EUR). Classic
OpenCart (Journal3 theme): `index.php?route=product/category&path=<id[_id...]>`
with 274 path ids on the homepage nav, so the shared base's NAV_URL leaf-walk
applies. Product cards carry a real `product_id=` PDP href, so the base `_item`
needs no override.
"""

from price_scraping.spiders._opencart_base import OpencartBaseSpider


class FnacandorraAdSpider(OpencartBaseSpider):
    name = "fnacandorra_ad"
    allowed_domains = ["fnac-andorra.com"]
    currency = "EUR"
    language = "es"
    NAV_URL = "https://fnac-andorra.com/"
    LIMIT = 100

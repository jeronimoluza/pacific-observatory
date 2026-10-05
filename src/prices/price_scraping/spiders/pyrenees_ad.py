"""Pyrenees Andorra (grans magatzems) food hall -- https://www.pyrenees.ad/alimentacio/.

Andorran department-store group (.ad). The /alimentacio/ shop is OpenCart
(Journal3 theme) with clean-SEO category URLs: no route=/path= ids, so the
shared base needs explicit CATEGORY_URLS. A top-level category page re-lists
its descendants' products (alls-cebes-i-patates: 16 cards vs 8 for its child
/patates), so only the top-level categories are walked; the url-keyed
DuplicationPipeline drops products reached through two parents.
Prices render as "6,99€" and parse through the base `normalize_price`.
"""

from price_scraping.spiders._opencart_base import OpencartBaseSpider

_BASE = "https://www.pyrenees.ad/alimentacio/"
_TOP = (
    "alls-cebes-i-patates amanides animals batuts-i-preparats-lactics "
    "begudes-alta-graduacio begudes-sense-alcohol carn-i-peix celler congelats "
    "cuits dietetica embotits esmorzars-dolcos-i-pa fleca-espicula "
    "foie-gras-confit formatges fruites fruites-i-verdures fumats-i-salaons "
    "higiene iogurt-i-postres lactics-i-ous lactis llet-i-begudes-vegetals "
    "mantega-margarina-nata menjar-internacional neteja-i-llar ous "
    "plats-preparats rebost ser-mes-eco verdures"
).split()


class PyreneesAdSpider(OpencartBaseSpider):
    name = "pyrenees_ad"
    allowed_domains = ["pyrenees.ad"]
    currency = "EUR"
    language = "ca"
    CATEGORY_URLS = tuple(f"{_BASE}{s}?limit=100" for s in _TOP)

    def _item(self, card, response):
        item = super()._item(card, response)
        if not item:
            return None
        url = item["url"].split("?")[0]
        parts = url.split("/alimentacio/", 1)[-1].split("/")
        item["url"] = url
        item["product_id"] = parts[-1]
        item["category"] = " > ".join(parts[:-1]) or None
        return item

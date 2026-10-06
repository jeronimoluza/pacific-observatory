"""Andorra Electronica -- https://andorraelectronica.com/es/.

Andorran electronics retailer (AD500, +376), PrestaShop with stock microdata
cards, so the shared PrestashopBaseSpider parses them unchanged. Its category
URLs are `/es/<slug>-<id>` (id TRAILING), which the base's `/<id>-<slug>`
discovery regex does not match -- left alone, the crawl only sees the
homepage carousel (3 items). The 21 department URLs from the nav are therefore
seeded explicitly; `?page=N` pagination and the card parser are the base's.
"""

import scrapy

from price_scraping.spiders._prestashop_base import PrestashopBaseSpider

_BASE = "https://andorraelectronica.com/es/"
_DEPARTMENTS = (
    "accesorios-6 altavoces-12 auriculares-13 auriculares-gaming-43 "
    "auriculares-in-ear-37 auriculares-on-ear-38 baterias-externas-39 "
    "cables-cargadores-40 dispositivos-inteligentes-90637 fundas-protectores-30 "
    "gadgets-tecnologicos-90640 hogar-inteligente-90638 iphone-apple-26 "
    "localizacion-rastreo-90639 moviles-10 moviles-ulefone-90636 "
    "moviles-xiaomi-28 samsung-galaxy-27 smartwatch-20 sonido-11 tablets-14"
).split()


class AndorraelectronicaAdSpider(PrestashopBaseSpider):
    name = "andorraelectronica_ad"
    allowed_domains = ["andorraelectronica.com"]
    currency = "EUR"
    language = "es"
    HOME_URL = _BASE

    async def start(self):
        self.seen_categories.add("")
        for d in _DEPARTMENTS:
            url = f"{_BASE}{d}"
            yield scrapy.Request(
                url, callback=self.parse_category, meta={"page": 1, "cat_url": url}
            )

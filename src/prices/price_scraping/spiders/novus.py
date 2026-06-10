"""
Spider for NOVUS (Ukraine) — novus.ua, via the zakaz.ua storefront JSON API.

NOVUS is a major Kyiv-region supermarket chain. See `_zakaz_base.py` for the
shared platform logic (Tier 1B JSON API, kopecks→UAH, no Playwright).
"""

from ._zakaz_base import ZakazBaseSpider


class NovusSpider(ZakazBaseSpider):
    name = "novus"
    chain = "novus"
    STORE_ID = "482010105"  # NOVUS SkyMall (a full-range store)

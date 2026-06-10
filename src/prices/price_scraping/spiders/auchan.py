"""
Spider for Auchan Ukraine — auchan.ua, via the zakaz.ua storefront JSON API.

See `_zakaz_base.py` for the shared platform logic (Tier 1B JSON API,
kopecks→UAH, no Playwright).
"""

from ._zakaz_base import ZakazBaseSpider


class AuchanSpider(ZakazBaseSpider):
    name = "auchan"
    chain = "auchan"
    STORE_ID = "48246401"  # Auchan Почайна DRIVE (full-range)

"""
Spider for METRO Ukraine — metro.ua, via the zakaz.ua storefront JSON API.

See `_zakaz_base.py` for the shared platform logic (Tier 1B JSON API,
kopecks→UAH, no Playwright).
"""

from ._zakaz_base import ZakazBaseSpider


class MetroSpider(ZakazBaseSpider):
    name = "metro"
    chain = "metro"
    STORE_ID = "48215610"  # METRO Позняки DRIVE (full-range)

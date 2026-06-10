"""
Spider for Tavria-V (Ukraine) — tavriav.ua, via the zakaz.ua storefront JSON API.

Tavria-V is a major southern-Ukraine supermarket chain. See `_zakaz_base.py`
for the shared platform logic (Tier 1B JSON API, kopecks→UAH, no Playwright).
"""

from ._zakaz_base import ZakazBaseSpider


class TavriavSpider(ZakazBaseSpider):
    name = "tavriav"
    chain = "tavriav"
    STORE_ID = "48221130"  # Таврія В Харків DRIVE (full-range)

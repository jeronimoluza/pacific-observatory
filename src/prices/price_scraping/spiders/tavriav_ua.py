"""Tavriav Ukraine -- https://tavriav.zakaz.ua/.

Tavria V -- southern/western Ukrainian supermarket chain (Odesa-founded).
The chain has no Kyiv store on the platform, so this spider pins the
Ivano-Frankivsk DRIVE store rather than the Kyiv convention used by the
other six; prices are that store's. 643 leaf categories / ~10.6k items.

Runs on the Zakaz.ua white-label e-grocery platform -- see
``_zakaz_base.ZakazBaseSpider`` for the API shape, the kopiyky->UAH price
scale, and the discovery note about ``zakaz.ua``'s 403 being confined to the
marketing root. Pinned store: Таврія В Івано-Франківськ DRIVE (store_id 482211004).
"""

from price_scraping.spiders._zakaz_base import ZakazBaseSpider


class TavriavUaSpider(ZakazBaseSpider):
    name = "tavriav_ua"

    STORE_ID = "482211004"
    STOREFRONT = "tavriav.zakaz.ua"

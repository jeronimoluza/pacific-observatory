"""ОнDe Ukraine -- https://onde.zakaz.ua/.

ОнDe -- Chernivtsi supermarket chain (western Ukraine). Only Chernivtsi
grocery catalog on the platform besides METRO.
639 leaf categories / ~9,732 declared items at the pinned store.

Runs on the Zakaz.ua white-label e-grocery platform -- see
``_zakaz_base.ZakazBaseSpider`` for the API shape, the kopiyky->UAH price
scale, and the discovery note about ``zakaz.ua``'s 403 being confined to the
marketing root. Pinned store: ОнDe DRIVE, Chernivtsi (store_id 482663071).
"""

from price_scraping.spiders._zakaz_base import ZakazBaseSpider


class OndeUaSpider(ZakazBaseSpider):
    name = "onde_ua"

    STORE_ID = "482663071"
    STOREFRONT = "onde.zakaz.ua"

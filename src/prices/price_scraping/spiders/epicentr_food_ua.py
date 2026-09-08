"""Epicentr FOOD Ukraine -- https://epicentr.zakaz.ua/.

Epicentr FOOD -- the grocery format of Epicentr K, Ukraine's largest
domestic retail group. channel: supermarket, not home-improvement: the
Zakaz.ua storefront carries ONLY the FOOD assortment (18 food/household top-
level departments, no DIY, no building materials), which is why the source
is named epicentr_food rather than epicentr.
624 leaf categories / ~21,478 declared items at the pinned store.

Runs on the Zakaz.ua white-label e-grocery platform -- see
``_zakaz_base.ZakazBaseSpider`` for the API shape, the kopiyky->UAH price
scale, and the discovery note about ``zakaz.ua``'s 403 being confined to the
marketing root. Pinned store: Epicentr FOOD Poliarna DRIVE, Kyiv (store_id 482374007).
"""

from price_scraping.spiders._zakaz_base import ZakazBaseSpider


class EpicentrFoodUaSpider(ZakazBaseSpider):
    name = "epicentr_food_ua"

    STORE_ID = "482374007"
    STOREFRONT = "epicentr.zakaz.ua"

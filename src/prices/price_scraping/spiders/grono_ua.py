"""GRONO Ukraine -- https://grono.zakaz.ua/.

GRONO -- Vinnytsia supermarket chain, with a large own-label production and
ready-meal range (Власне виробництво GRONO, Gronokitchen+).
524 leaf categories / ~7,215 declared items at the pinned store.

Runs on the Zakaz.ua white-label e-grocery platform -- see
``_zakaz_base.ZakazBaseSpider`` for the API shape, the kopiyky->UAH price
scale, and the discovery note about ``zakaz.ua``'s 403 being confined to the
marketing root. Pinned store: Grono DRIVE, Vinnytsia (store_id 482476001).
"""

from price_scraping.spiders._zakaz_base import ZakazBaseSpider


class GronoUaSpider(ZakazBaseSpider):
    name = "grono_ua"

    STORE_ID = "482476001"
    STOREFRONT = "grono.zakaz.ua"

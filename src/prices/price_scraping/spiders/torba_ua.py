"""Торба Ukraine -- https://torba.zakaz.ua/.

Торба -- western-Ukrainian supermarket chain (Rivne, Chernivtsi, Ivano-
Frankivsk). Rivne is pinned because it carries the largest of the three
catalogs (644 leaves vs 518 / 455).
644 leaf categories / ~8,922 declared items at the pinned store.

Runs on the Zakaz.ua white-label e-grocery platform -- see
``_zakaz_base.ZakazBaseSpider`` for the API shape, the kopiyky->UAH price
scale, and the discovery note about ``zakaz.ua``'s 403 being confined to the
marketing root. Pinned store: Torba Rivne (store_id 482867220).
"""

from price_scraping.spiders._zakaz_base import ZakazBaseSpider


class TorbaUaSpider(ZakazBaseSpider):
    name = "torba_ua"

    STORE_ID = "482867220"
    STOREFRONT = "torba.zakaz.ua"

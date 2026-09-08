"""Auchan Ukraine -- https://auchan.zakaz.ua/.

Auchan Ukraine -- French-owned hypermarket chain. `auchan.ua` is a full
client-side Apollo/GraphQL SPA (wave 12 deferred it as a Playwright job);
its Zakaz.ua storefront exposes the same assortment over a plain JSON API,
so no browser is needed. 1,040 leaf categories / ~25.8k declared items --
the widest catalog of the seven Ukrainian Zakaz chains built here.

Runs on the Zakaz.ua white-label e-grocery platform -- see
``_zakaz_base.ZakazBaseSpider`` for the API shape, the kopiyky->UAH price
scale, and the discovery note about ``zakaz.ua``'s 403 being confined to the
marketing root. Pinned store: Auchan Почайна DRIVE, Kyiv (store_id 48246401).
"""

from price_scraping.spiders._zakaz_base import ZakazBaseSpider


class AuchanUaSpider(ZakazBaseSpider):
    name = "auchan_ua"

    STORE_ID = "48246401"
    STOREFRONT = "auchan.zakaz.ua"

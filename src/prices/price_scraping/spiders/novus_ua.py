"""Novus Ukraine -- https://novus.zakaz.ua/.

NOVUS -- Lithuanian-owned modern supermarket/hypermarket chain, one of
Kyiv's three largest grocery operators. `novus.ua` itself is a JS-hydrated
marketing storefront with no server-rendered category nav (the reason the
wave-12 pass could not build it); the transactional catalog lives on the
Zakaz.ua platform. 967 leaf categories / ~19.3k declared items.

Runs on the Zakaz.ua white-label e-grocery platform -- see
``_zakaz_base.ZakazBaseSpider`` for the API shape, the kopiyky->UAH price
scale, and the discovery note about ``zakaz.ua``'s 403 being confined to the
marketing root. Pinned store: NOVUS SkyMall DRIVE, Kyiv (store_id 482010105).
"""

from price_scraping.spiders._zakaz_base import ZakazBaseSpider


class NovusUaSpider(ZakazBaseSpider):
    name = "novus_ua"

    STORE_ID = "482010105"
    STOREFRONT = "novus.zakaz.ua"

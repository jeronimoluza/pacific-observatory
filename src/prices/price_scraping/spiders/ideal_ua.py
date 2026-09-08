"""Ідеал Ukraine -- https://ideal.zakaz.ua/.

Ідеал -- Odesa supermarket chain. Second-largest non-Kyiv catalog on the
platform and the deepest Odesa coverage after tavriav_ua.
720 leaf categories / ~18,220 declared items at the pinned store.

Runs on the Zakaz.ua white-label e-grocery platform -- see
``_zakaz_base.ZakazBaseSpider`` for the API shape, the kopiyky->UAH price
scale, and the discovery note about ``zakaz.ua``'s 403 being confined to the
marketing root. Pinned store: Ideal Odesa (store_id 482596001).
"""

from price_scraping.spiders._zakaz_base import ZakazBaseSpider


class IdealUaSpider(ZakazBaseSpider):
    name = "ideal_ua"

    STORE_ID = "482596001"
    STOREFRONT = "ideal.zakaz.ua"

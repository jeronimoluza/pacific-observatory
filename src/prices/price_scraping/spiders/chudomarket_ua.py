"""Чудо Маркет Ukraine -- https://chudomarket.zakaz.ua/.

Чудо Маркет -- Kharkiv supermarket chain. Verified independent of the
Kharkiv/Vostorg pair: sampled shelves share SKUs but 0 identical prices, so
this is a separate price quote.
733 leaf categories / ~9,526 declared items at the pinned store.

Runs on the Zakaz.ua white-label e-grocery platform -- see
``_zakaz_base.ZakazBaseSpider`` for the API shape, the kopiyky->UAH price
scale, and the discovery note about ``zakaz.ua``'s 403 being confined to the
marketing root. Pinned store: Chudo Market, Kharkiv (store_id 482330018).
"""

from price_scraping.spiders._zakaz_base import ZakazBaseSpider


class ChudomarketUaSpider(ZakazBaseSpider):
    name = "chudomarket_ua"

    STORE_ID = "482330018"
    STOREFRONT = "chudomarket.zakaz.ua"

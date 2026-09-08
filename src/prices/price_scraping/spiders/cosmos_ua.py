"""КОСМОС Ukraine -- https://cosmos.zakaz.ua/.

КОСМОС -- Ukrainian supermarket chain trading in Kyiv and Odesa. Verified
independent of the Megamarket banners: sampled shelves share only ~25% of
SKUs with megamarket_ua and 0 identical prices, so this is a genuinely
separate price quote.
695 leaf categories / ~14,084 declared items at the pinned store.

Runs on the Zakaz.ua white-label e-grocery platform -- see
``_zakaz_base.ZakazBaseSpider`` for the API shape, the kopiyky->UAH price
scale, and the discovery note about ``zakaz.ua``'s 403 being confined to the
marketing root. Pinned store: Cosmos Kyiv DRIVE (store_id 48225531).
"""

from price_scraping.spiders._zakaz_base import ZakazBaseSpider


class CosmosUaSpider(ZakazBaseSpider):
    name = "cosmos_ua"

    STORE_ID = "48225531"
    STOREFRONT = "cosmos.zakaz.ua"

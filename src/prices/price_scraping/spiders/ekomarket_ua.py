"""Ekomarket Ukraine -- https://ekomarket.zakaz.ua/.

Eko-market -- Ukrainian mid-market supermarket chain. 604 leaf categories
/ ~8.1k declared items, the smallest of the seven built here.

Runs on the Zakaz.ua white-label e-grocery platform -- see
``_zakaz_base.ZakazBaseSpider`` for the API shape, the kopiyky->UAH price
scale, and the discovery note about ``zakaz.ua``'s 403 being confined to the
marketing root. Pinned store: ЕкоМаркет Огієнка DRIVE, Kyiv (store_id 482800030).
"""

from price_scraping.spiders._zakaz_base import ZakazBaseSpider


class EkomarketUaSpider(ZakazBaseSpider):
    name = "ekomarket_ua"

    STORE_ID = "482800030"
    STOREFRONT = "ekomarket.zakaz.ua"

"""Metro Ukraine -- https://metro.zakaz.ua/.

METRO Cash & Carry Ukraine -- cash-and-carry wholesale. Priced and sold
by the case/tray as well as singles, so `channel: wholesale`, matching the
METRO manifests in other countries; kept because wholesale unit prices are
a distinct PPP layer from the retail chains, not a substitute for them.
768 leaf categories / ~10.7k declared items.

Runs on the Zakaz.ua white-label e-grocery platform -- see
``_zakaz_base.ZakazBaseSpider`` for the API shape, the kopiyky->UAH price
scale, and the discovery note about ``zakaz.ua``'s 403 being confined to the
marketing root. Pinned store: METRO Позняки DRIVE, Kyiv (store_id 48215610).
"""

from price_scraping.spiders._zakaz_base import ZakazBaseSpider


class MetroUaSpider(ZakazBaseSpider):
    name = "metro_ua"

    STORE_ID = "48215610"
    STOREFRONT = "metro.zakaz.ua"

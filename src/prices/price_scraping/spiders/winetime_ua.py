"""Winetime Ukraine -- https://winetime.zakaz.ua/.

WineTime -- Ukraine's largest specialist wine-and-spirits retail chain,
with a delicatessen/gourmet-food side. Onboarded specifically for COICOP
division 02 (alcoholic beverages) depth, which the general grocers cover
only shallowly: 473 leaf categories / ~10.3k declared items, dominated by
wine, spirits, beer and champagne, plus cheese/charcuterie/coffee aisles.
`channel: specialty-food` follows the `denner_ch` wine-shop precedent --
the enum has no alcohol-specific value.

Products carry an `is_alcohol` flag in the API payload; it is not used to
filter, since the deli aisles are genuine division-01 coverage.

Runs on the Zakaz.ua white-label e-grocery platform -- see
``_zakaz_base.ZakazBaseSpider`` for the API shape, the kopiyky->UAH price
scale, and the discovery note about ``zakaz.ua``'s 403 being confined to the
marketing root. Pinned store: WineTime Бажана DRIVE, Kyiv (store_id 482550001).
"""

from price_scraping.spiders._zakaz_base import ZakazBaseSpider


class WinetimeUaSpider(ZakazBaseSpider):
    name = "winetime_ua"

    STORE_ID = "482550001"
    STOREFRONT = "winetime.zakaz.ua"

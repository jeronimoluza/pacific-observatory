"""MEGAMARKET group Ukraine -- four Kyiv banners of one operator, one source.

MEGAMARKET, ULTRAMARKET, Za Raz and AlcoHub are four storefronts of a single
Kyiv operator occupying the same three addresses (Surykova / Kosmopolit /
Podol). They are NOT independent price quotes: whenever the same EAN appears
in two of them it carries an identical price (measured 2026-09-06 --
megamarket x ultramarket 1/1, ultramarket x zaraz 12/12, zaraz x alcohub
20/20 identical; every cross-city pair against the Kharkiv hub was 0%
identical, so the effect is the operator, not the platform).

Onboarded as ONE source because each banner still contributes a distinct
slice of assortment (AlcoHub is an alcohol specialist with only 136 leaf
categories against MEGAMARKET's 781), but four separate sources would have
quadruple-counted every shared SKU -- `publish.py` aggregates on
(coicop_code, country, standard_unit) with `n_obs = size` and no source
dimension, so duplicated quotes both drag the median and can push a cell past
MIN_OBS_PER_CELL on the strength of one real observation.

`web_url` is per-storefront (`megamarket.zakaz.ua/...` vs
`ultramarket.zakaz.ua/...` for the same EAN), so the DuplicationPipeline's
url-dedup cannot collapse these; the base class dedups on ean/sku instead.
First store listed wins.

See `_zakaz_base.ZakazBaseSpider` for the API shape and the kopiyky->UAH
price scale.
"""

from price_scraping.spiders._zakaz_base import ZakazBaseSpider


class MegamarketGroupUaSpider(ZakazBaseSpider):
    name = "megamarket_group_ua"

    # Ordered: flagship banner first, so its permalink/title wins a tie.
    STORES = {
        "482676003": "megamarket.zakaz.ua",  # MEGAMARKET Поділ
        "48277602": "ultramarket.zakaz.ua",  # ULTRAMARKET Kosmopolit DRIVE
        "482778002": "zaraz.zakaz.ua",  # Za Raz
        "482779002": "alcohub.zakaz.ua",  # AlcoHub (alcohol specialist)
    }
    STOREFRONT = "megamarket.zakaz.ua"  # Referer fallback

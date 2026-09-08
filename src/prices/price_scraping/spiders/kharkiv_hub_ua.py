"""Kharkiv hub Ukraine -- Kharkiv Market + Vostorg, one operator, one source.

Both storefronts are served from the same Klochkivska hub: 620 of 621
category slugs are identical, and every shared EAN carries an identical price
(29/29 measured 2026-09-06, against 0% identical for every pair spanning this
hub and the Kyiv MEGAMARKET group). Treating them as two sources would have
double-counted the shared assortment in `publish.py`'s `n_obs`.

`web_url` is per-storefront, so url-dedup cannot collapse them; the base class
dedups on ean/sku. First store listed wins.

See `_zakaz_base.ZakazBaseSpider` for the API shape and the kopiyky->UAH
price scale.
"""

from price_scraping.spiders._zakaz_base import ZakazBaseSpider


class KharkivHubUaSpider(ZakazBaseSpider):
    name = "kharkiv_hub_ua"

    STORES = {
        "482320001": "kharkiv.zakaz.ua",  # Kharkiv Market, Klochkivska
        "48231001": "vostorg.zakaz.ua",  # Vostorg, same hub
    }
    STOREFRONT = "kharkiv.zakaz.ua"  # Referer fallback

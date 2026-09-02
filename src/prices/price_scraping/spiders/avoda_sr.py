"""
Avoda (Suriname) -- https://www.avoda.sr/.

"De online supermarkt van Suriname" -- HEM Suriname N.V.'s SRD-priced
retail webshop (1,224 SKUs confirmed live 2026-09-01 via the WooCommerce
Store API). Real grocery categories present: Levensmiddelen (266),
Conserven (50), Koffie/thee/cacao (43), Koel- en vriesproducten (23),
Soepen/sauzen/smaakmakers (33), Broodbeleg en ontbijtgranen (28),
Koek/snoep/snacks (28), Alcoholische/Non-alcoholische dranken (13) --
alongside household/personal-care lines. channel: supermarket.

Freshness check (rule: SRD went ~3.3/USD in 2020 to ~38/USD by 2024):
Nature Soft Bathroom Tissue 2-Ply 24 Rolls = SRD 330.07 as of 2026-09-01,
consistent with the post-devaluation exchange rate (~USD 8-9 equivalent
for a 24-roll bulk pack) -- not a stale pre-devaluation cache.

NOT the same source as now2su.com: HEM Suriname N.V.'s own webshops page
(https://www.hem.sr/nl/webshops) explicitly lists BOTH avoda.sr AND
now2su.com as its own storefronts. A 300-item sample pulled from each
Store API on 2026-09-01 found 277/300 (92.3%) identical product names --
confirmed same catalog/backend, not independently verified retail
footprints. now2su.com was deliberately NOT onboarded as a separate
source to avoid double-counting this shelf (see rule 19 in the wave-13
brief); it is priced in EUR for the diaspora-order/pickup-in-Suriname
market, avoda.sr in SRD for domestic shoppers.

Full-catalog run (2026-09-01, 1,226 items): 2 rows carried price=0,
both marked `is_in_stock=False` (out-of-stock items with the price
wiped upstream, e.g. "L'Oreal Color Vibrancy Purple Conditioner
150ml") -- same artifact already documented and dropped in telesur_sr
on this same storefront family. Dropped here for consistency rather
than emitted as a fabricated 0-price row.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class AvodaSrSpider(WooBaseSpider):
    name = "avoda_sr"
    allowed_domains = ["www.avoda.sr"]
    currency = "SRD"
    language = "nl"
    BASE_URL = "https://www.avoda.sr/wp-json/wc/store/v1/products"

    def _item(self, p: dict):
        item = super()._item(p)
        if item and float(item["price"]) <= 0:
            return None
        return item

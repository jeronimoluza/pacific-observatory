"""
Nana Hama (Syria) -- https://nana.dex.sy/
("نعناع حماه" -- fresh fruit and vegetables, delivered daily in Hama)

dex.sy-hosted storefront; see _dex_sy_base.py for the shared API contract
and the measurement notes.

MEASURED 2026-09-12: /api/products meta.total=37, totalPages=2 at
limit=24; page 1 vs page 2 productId sets disjoint (24 + 13, zero
overlap). Sample product: "تين" (figs) at 80, stockQuantity 100.

CURRENCY: SYP, read from this store's own `"baseCurrency":"SYP"` in the
homepage RSC flight payload on 2026-09-12 -- not from the .sy TLD.

CATALOG: greengrocer -- fresh fruit, vegetables and herbs. That is COICOP
01.1.6 / 01.1.7 territory, but the catalog also carries eggs, dairy and
pantry lines, so coicop_codes is left unset in the manifest and the
classifier assigns the leaf per product.

Page family: API.
"""

from price_scraping.spiders._dex_sy_base import DexSyBaseSpider


class NanaDexSpider(DexSyBaseSpider):
    name = "nana_dex"
    allowed_domains = ["nana.dex.sy"]
    STORE_HOST = "nana.dex.sy"
    currency = "SYP"
    language = "ar"

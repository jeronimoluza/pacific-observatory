"""
Karazzah (Syria) -- https://karazzah.dex.sy/
(Hama accessories / jewellery / gifts store)

dex.sy-hosted storefront; see _dex_sy_base.py for the shared API contract
and the measurement notes.

MEASURED 2026-09-12: /api/products meta.total=37, totalPages=2 at
limit=24; page 1 vs page 2 productId sets disjoint (24 + 13, zero
overlap). Sample product: "طقم جوهرة الحب" (a jewellery set), sku
"KH-192.75".

CURRENCY: SYP, read from this store's own `"baseCurrency":"SYP"` in the
homepage RSC flight payload on 2026-09-12.

CATALOG: costume jewellery, bracelets, necklaces, sets and small gift
items -- COICOP 13.1 (personal effects n.e.c. / jewellery) with a gift
tail that can also land in 09.3. Kept wide (coicop_codes unset) rather
than forcing 13.1 on the gift lines.

Page family: API.
"""

from price_scraping.spiders._dex_sy_base import DexSyBaseSpider


class KarazzahDexSpider(DexSyBaseSpider):
    name = "karazzah_dex"
    allowed_domains = ["karazzah.dex.sy"]
    STORE_HOST = "karazzah.dex.sy"
    currency = "SYP"
    language = "ar"

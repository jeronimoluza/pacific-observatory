"""
MID / Middle East Electrical Appliances (Syria) -- https://mid.dex.sy/
("معرض الشرق الأوسط للأدوات الكهربائية")

dex.sy-hosted storefront; see _dex_sy_base.py for the shared API contract
and the measurement notes.

MEASURED 2026-09-12: /api/products meta.total=49, totalPages=3 at
limit=24; page 1 vs page 2 productId sets disjoint (24 + 24, zero
overlap). Sample product: "مراوح" (fans).

CURRENCY: SYP, read from this store's own `"baseCurrency":"SYP"` in the
homepage RSC flight payload on 2026-09-12.

CATALOG: household electricals -- fans, refrigerators, beverage coolers,
air coolers, electric grills and cookers, juicers, washing machines,
kettles, meat grinders, gas ovens, food processors, vacuum cleaners,
steam irons, coffee makers, plus kitchen and plumbing tools. Spans COICOP
05.3 (appliances), 05.4 (glassware/utensils) and 05.5 (tools), so
coicop_codes is left unset -- wide by the narrowness rule.

Page family: API.
"""

from price_scraping.spiders._dex_sy_base import DexSyBaseSpider


class MidDexSpider(DexSyBaseSpider):
    name = "mid_dex"
    allowed_domains = ["mid.dex.sy"]
    STORE_HOST = "mid.dex.sy"
    currency = "SYP"
    language = "ar"

"""
Spider for FreshMart (Azerbaijan) — https://freshmart.az/en-gb/.

OpenCart storefront with clean-SEO category URLs (no route=/path= params),
so this reuses `_opencart_base.py`'s CATEGORY_URLS mode rather than its
NAV_URL auto-discovery mode. The 53 leaf subcategory paths below were
pulled from the site's own top nav (2026-08-06); `product-thumb` cards
carry name in an `h4 a` and price in `.price-new` -- both already covered
by the base class's selector list. Re-verified live: /en-gb/catalog/
meyve-ve-terevez/meyve -> 200, real cards e.g. 'BANAN KQ' 3.39₼
(price-new, price-old 3.49₼ struck through), `?page=2` pagination
confirmed present.

Product names/categories are Azerbaijani (Latin script) despite the
en-gb URL prefix -- language set to az, not the shard's en starting point.
"""

from ._opencart_base import OpencartBaseSpider

_BASE = "https://freshmart.az/en-gb/catalog"
_LEAF_SLUGS = (
    "atistirmaliq/cerezler",
    "atistirmaliq/cips",
    "atistirmaliq/keks-ve-biskvit",
    "atistirmaliq/saqqiz",
    "atistirmaliq/sokoladlar",
    "cay-kofe-seker/cay",
    "cay-kofe-seker/kofe",
    "cay-kofe-seker/seker",
    "corek-ve-firin/corekler",
    "corek-ve-firin/sirniyyatlar",
    "corek-ve-firin/tortlar",
    "corek-ve-firin/un-memulatlari",
    "deterjan-ve-temizlik/paltar-yuma",
    "deterjan-ve-temizlik/qab-yuma",
    "deterjan-ve-temizlik/temizlik-kagizlari",
    "dondurma/dondurma",
    "esas-qida-mehsullari/bakliyyat",
    "esas-qida-mehsullari/duyu",
    "esas-qida-mehsullari/makaron",
    "esas-qida-mehsullari/un",
    "esas-qida-mehsullari/yag",
    "et-toyuq-baliq/deniz-mehsullari",
    "et-toyuq-baliq/kolbasa-ve-sosis",
    "et-toyuq-baliq/qirmizi-et",
    "et-toyuq-baliq/toyuq-eti",
    "ev-ve-bag/dekorasiya",
    "ev-ve-bag/metbex-esyalari",
    "ev-ve-bag/tekstil",
    "i-ckiler/enerji-ickileri",
    "i-ckiler/meyve-sulari",
    "i-ckiler/qazli-ickiler",
    "i-ckiler/su",
    "konserv-ve-soslar/edviyyat",
    "konserv-ve-soslar/konservler",
    "konserv-ve-soslar/soslar",
    "konserv-ve-soslar/tursular",
    "meyve-ve-terevez/goyerti-ve-yarpaq",
    "meyve-ve-terevez/meyve",
    "meyve-ve-terevez/quru-meyve",
    "meyve-ve-terevez/terevez",
    "petshop/i-t-yemi",
    "petshop/pisik-yemi",
    "sexsi-baxim/agiz-baximi",
    "sexsi-baxim/dus-ve-sabun",
    "sexsi-baxim/sac-baximi",
    "sud-mehsullari/kere-yagi",
    "sud-mehsullari/pendir",
    "sud-mehsullari/qatiq",
    "sud-mehsullari/sud",
    "sud-mehsullari/xama-ve-qaymaq",
    "usaq-dunyasi/oyuncaqlar",
    "usaq-dunyasi/usaq-bezi",
    "usaq-dunyasi/usaq-qidasi",
)


class FreshmartAzSpider(OpencartBaseSpider):
    name = "freshmart_az"
    allowed_domains = ["freshmart.az"]
    currency = "AZN"
    language = "az"
    CATEGORY_URLS = tuple(f"{_BASE}/{slug}" for slug in _LEAF_SLUGS)

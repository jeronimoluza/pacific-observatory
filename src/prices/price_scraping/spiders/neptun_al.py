"""
Spider for Neptun (Albania) -- https://www.neptun.al/.

.NET MVC backend behind a Nuxt-ish SPA shell. The raw category page HTML
(e.g. /Celular.nspx) carries no product/price markup -- confirmed live
2026-08-17, matching the original probe -- but Playwright network tracing
found the real data source: an AngularJS widget same-origin POSTs to
NeptunCategories/LoadProductsForCategory with a JSON `model` body
(CategoryId/CurrentPage/ItemsPerPage/Sort), which returns the full product
batch (name, price, currency label, product code) as JSON.

Category ids are NOT guessable from the .nspx slugs (most are opaque, e.g.
Celular.nspx -> CategoryId 143). They come from a live discovery sweep:
each .nspx category page embeds its own CategoryId in a
`data-initialSearchModel` attribute, so a probe of CategoryId 1-699
against LoadProductsForCategory (ShowAllProducts=true) found 282 ids that
return a nonempty product batch; those 282 ids are hardcoded below as the
discovered category set (17,862 products total across them).

Enumerability proven: CategoryId=173 (the largest, 1081 items),
CurrentPage=1 vs CurrentPage=2 (ItemsPerPage=20) return 20 + 20 distinct
product ids, zero overlap.

Currency is Albanian Lek; the API returns the display label "LEKË", not an
ISO code, so `self.currency` ("ALL") is used directly rather than the raw
API string.
"""

import json
from datetime import datetime, timezone

import scrapy

_URL = "https://www.neptun.al/NeptunCategories/LoadProductsForCategory"
_ITEMS_PER_PAGE = 20
_MAX_PAGES = 20

# Discovered live 2026-08-17: CategoryId values in [1, 699] whose
# LoadProductsForCategory response has TotalItems > 0.
_CATEGORY_IDS = [
    6,
    19,
    20,
    21,
    22,
    23,
    24,
    25,
    26,
    28,
    29,
    31,
    32,
    33,
    34,
    35,
    36,
    37,
    38,
    39,
    40,
    41,
    43,
    45,
    46,
    47,
    48,
    49,
    51,
    53,
    54,
    56,
    59,
    60,
    61,
    62,
    63,
    68,
    73,
    75,
    76,
    78,
    80,
    81,
    82,
    83,
    84,
    85,
    90,
    92,
    93,
    94,
    96,
    98,
    99,
    100,
    102,
    103,
    105,
    106,
    107,
    109,
    110,
    111,
    112,
    116,
    118,
    120,
    122,
    123,
    124,
    125,
    127,
    128,
    130,
    131,
    134,
    135,
    136,
    138,
    139,
    140,
    142,
    143,
    144,
    145,
    147,
    148,
    149,
    150,
    157,
    158,
    162,
    163,
    165,
    170,
    173,
    218,
    219,
    220,
    221,
    223,
    224,
    225,
    226,
    227,
    236,
    237,
    238,
    239,
    240,
    241,
    243,
    244,
    245,
    246,
    247,
    248,
    249,
    250,
    251,
    258,
    260,
    261,
    276,
    278,
    282,
    321,
    323,
    336,
    338,
    349,
    354,
    355,
    356,
    361,
    362,
    363,
    365,
    366,
    367,
    368,
    369,
    370,
    371,
    372,
    373,
    374,
    375,
    376,
    377,
    378,
    379,
    380,
    381,
    383,
    384,
    385,
    386,
    387,
    388,
    389,
    390,
    391,
    392,
    393,
    394,
    395,
    396,
    397,
    398,
    399,
    400,
    404,
    413,
    414,
    415,
    416,
    417,
    420,
    421,
    422,
    425,
    454,
    457,
    465,
    466,
    473,
    474,
    475,
    477,
    479,
    480,
    481,
    482,
    484,
    485,
    486,
    487,
    488,
    489,
    490,
    491,
    495,
    496,
    497,
    498,
    499,
    500,
    501,
    502,
    504,
    505,
    507,
    508,
    525,
    526,
    530,
    532,
    535,
    537,
    538,
    539,
    540,
    543,
    544,
    545,
    546,
    547,
    548,
    549,
    550,
    551,
    556,
    558,
    561,
    562,
    563,
    564,
    566,
    567,
    568,
    569,
    570,
    575,
    578,
    579,
    580,
    583,
    587,
    588,
    589,
    590,
    595,
    596,
    597,
    598,
    600,
    601,
    602,
    603,
    604,
    605,
    606,
    607,
    608,
    609,
    610,
    611,
    612,
    613,
    614,
    615,
    617,
    618,
    619,
    620,
    621,
    622,
    623,
    624,
    625,
]


class NeptunAlSpider(scrapy.Spider):
    name = "neptun_al"
    allowed_domains = ["neptun.al"]
    currency = "ALL"
    language = "sq"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }
    IMPERSONATE_PROFILE = "chrome124"

    async def start(self):
        for cid in _CATEGORY_IDS:
            yield self._page_request(cid, 1)

    def _page_request(self, category_id: int, page: int):
        body = {
            "model": {
                "TotalItems": 0,
                "CurrentPage": page,
                "ItemsPerPage": _ITEMS_PER_PAGE,
                "Sort": 4,
                "CategoryId": category_id,
                "Recomended": False,
                "ShowAllProducts": True,
            }
        }
        return scrapy.Request(
            _URL,
            method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps(body),
            callback=self.parse_page,
            meta={
                "category_id": category_id,
                "page": page,
                "impersonate": self.IMPERSONATE_PROFILE,
            },
        )

    def parse_page(self, response):
        try:
            data = response.json()
        except ValueError:
            return
        batch = data.get("Batch") or {}
        items = batch.get("Items") or []
        category_id = response.meta["category_id"]
        page = response.meta["page"]
        for p in items:
            item = self._item(p)
            if item:
                yield item
        total = (batch.get("Config") or {}).get("TotalItems", 0)
        if items and page * _ITEMS_PER_PAGE < total and page < _MAX_PAGES:
            yield self._page_request(category_id, page + 1)

    def _item(self, p: dict):
        name = (p.get("Title") or "").strip()
        price = p.get("ActualPrice")
        if not name or price is None:
            return None
        url_slug = p.get("Url") or ""
        return {
            "product_id": str(p.get("Id") or ""),
            "product_name": name[:500],
            "category": ((p.get("Category") or {}).get("Name")) or None,
            "price": str(price),
            "currency": self.currency,
            "available": bool(p.get("AvailableWebshop") or p.get("AvailableOnline")),
            "url": f"https://www.neptun.al/{url_slug}.nspx" if url_slug else "",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

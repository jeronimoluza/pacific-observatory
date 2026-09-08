"""
Spider for Hofer Slovenia (Aldi Sued) — https://www.hofer.si/.

Nuxt 3 SSR storefront (distinct platform from Lidl's Vue/data-grid-data
setup already used for lidl_si/lidl_rs). Category pages under
/izdelki/<slug>/k/<id> embed the full product batch for that page in a
`<script type="application/json" data-nuxt-data="nuxt-app" id="__NUXT_DATA__">`
tag: Nuxt's flattened "devalue" payload format, a single JSON array where any
non-negative integer found as a value is itself an index back into the same
array (one level of dereferencing is enough here -- `_deref()` below).

Re-verified live 2026-09-06: GET
/izdelki/meso-mesni-izdelki-in-ribe/k/1588161418378160 -> 200, 529KB, 44
product dicts recovered (key set {sku, name, price, ...}). Sample: sku
000000000000191385 'File lososa' (GOLDEN SEAFOOD) price.amountRelevant=261
-> EUR 2.61. Product PDP lives at /izdelek/<urlSlugText>-<sku>.

No page-2/pagination param was found (`?page=2` returns zero product dicts,
same "bounded first SSR batch" shape as lidl_si) -- this walks 34 category
hub pages once each, not a deep-paginated full catalog. 34 categories from
the homepage's own top-nav (`/izdelki/*/k/*`) span the full basket:
alcohol, non-alc drinks, meat/fish, dairy/eggs, bakery, cleaning, personal
care, pet, electronics, garden, etc.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.hofer.si"

_CATEGORIES = [
    "alkoholne-pijace/k/1588161418378260",
    "bio-izdelki/k/1588161418378100",
    "brezalkoholne-pijace/k/1588161418378250",
    "cistila/k/1588161418378520",
    "delavnica-in-orodje/k/1588161418378490",
    "elektronika/k/1588161418378430",
    "izdelki-brez-laktoze/k/1588161418378120",
    "izdelki-za-dom-in-gospodinjstvo/k/1588161418378270",
    "kakovost-iz-slovenije/k/1588161418378130",
    "konzervirana-hrana-in-pripravljeni-obroki/k/1588161418378210",
    "meso-mesni-izdelki-in-ribe/k/1588161418378160",
    "mleko-mlecni-izdelki-in-jajca/k/1588161418378170",
    "novo/k/1588161418378370",
    "oblacila-obutev-in-modni-dodatki/k/1588161418378400",
    "okusi-sveta/k/1588161418378380",
    "omake-olja-kis-in-zacimbe/k/1588161418378200",
    "osebna-nega/k/1588161418378280",
    "otroska-prehrana-in-nega/k/1588161418378290",
    "pekovski-izdelki-namazi-in-kosmici/k/1588161418378180",
    "prazniki-in-sezonski-izdelki/k/1588161418378470",
    "prehranska-dopolnila/k/1588161418378390",
    "roze-in-rezano-cvetje/k/1588161418378350",
    "sladki-in-slani-prigrizki/k/1588161418378240",
    "sladoledi-in-sorbeti/k/1588161432231111",
    "sport-in-prosti-cas/k/1588161418378480",
    "testenine-riz-in-strocnice/k/1588161418378190",
    "vegansko-in-vegetarijansko/k/1588161418378140",
    "vrt-in-okolica/k/1588161418378510",
    "vse-za-peko/k/1588161418378230",
    "vse-za-solo/k/1588161418378460",
    "vse-za-zar/k/1588161418378330",
    "za-male-zivali/k/1588161418378300",
    "zamrznjeni-izdelki/k/1588161418378220",
    "izdelki/k/1588161418378100",
]

_NUXT_DATA_RE = re.compile(
    r'<script type="application/json" data-nuxt-data="nuxt-app" data-ssr="true" id="__NUXT_DATA__">'
)


def _deref(arr, v, depth=0):
    if depth > 3:
        return v
    if isinstance(v, int) and 0 <= v < len(arr):
        return arr[v]
    return v


class HoferSiSpider(scrapy.Spider):
    name = "hofer_si"
    allowed_domains = ["hofer.si"]
    currency = "EUR"
    language = "sl"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for cat in _CATEGORIES:
            slug = cat.split("/")[0]
            yield scrapy.Request(
                f"{_BASE}/izdelki/{cat}",
                callback=self.parse_category,
                meta={"category": slug},
            )

    def parse_category(self, response):
        category = response.meta["category"]
        m = _NUXT_DATA_RE.search(response.text)
        if not m:
            logger.warning(f"hofer_si: no __NUXT_DATA__ at {response.url}")
            return
        end = response.text.find("</script>", m.end())
        try:
            arr = json.loads(response.text[m.end() : end])
        except ValueError:
            logger.warning(f"hofer_si: bad JSON at {response.url}")
            return
        prod_idxs = [
            i
            for i, v in enumerate(arr)
            if isinstance(v, dict) and "sku" in v and "name" in v and "price" in v
        ]
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for i in prod_idxs:
            item = self._item(arr, arr[i], category, scraped_at)
            if item:
                n += 1
                yield item
        logger.info(f"hofer_si: {category} items={n}")

    def _item(self, arr, p: dict, category: str, scraped_at: str):
        sku = _deref(arr, p.get("sku"))
        name = _deref(arr, p.get("name"))
        if not sku or not name:
            return None
        price_obj = _deref(arr, p.get("price"))
        if not isinstance(price_obj, dict):
            return None
        amount = _deref(arr, price_obj.get("amountRelevant"))
        if not isinstance(amount, (int, float)):
            return None
        price = amount / 100.0
        slug = _deref(arr, p.get("urlSlugText")) or ""
        return {
            "product_id": str(sku),
            "product_name": str(name).strip()[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": f"{_BASE}/izdelek/{slug}-{sku}" if slug else f"{_BASE}/izdelki/{category}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

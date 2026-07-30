"""
Spider for Alfagift (Indonesia) - alfagift.id, the online storefront for the
Alfamart minimarket chain.

Uses the storefront's own JSON gateway (webcommerce-gw.alfagift.id) directly -
no auth token required, just a handful of custom headers the Nuxt SPA sends on
every call (fingerprint / devicetype / devicemodel / trxid / latitude /
longitude). No Authorization header is needed; a static fingerprint value and
a random numeric trxid per request are accepted.

There is no category-browse endpoint (guessed `/v2/products/category`,
`/v2/categories/{id}` etc. all 404/500) - the only way to reach the catalog is
`/v2/products/searches?keyword=...`, which the storefront's own search box
calls. That endpoint hard-caps at 100 rows per keyword and does NOT support
paging past start=0 (any start>0 returns an empty page even when totalData
says more rows exist), so we shard on a fixed keyword list instead of walking
pages. Alfamart is a convenience-store catalog (packaged/branded goods) - it
does not stock raw fresh produce (salak/rambutan/singkong/ubi jalar all return
0), but it is a strong hit for packaged cooking oil (minyak goreng: 48 SKUs of
real brands) plus broad general FMCG (dairy, snacks, instant noodles, personal
care, beverages).
"""

import json
import logging
import random
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://webcommerce-gw.alfagift.id"
_SEARCH = _BASE + "/v2/products/searches"
_PAGE_CAP = 100

# Static fingerprint observed from a real browser session; the gateway does
# not appear to validate it against a server-side session, only requires the
# header to be present and well-formed.
_FINGERPRINT = "E5tMISZt4EvsIcInOjZUG0EJbaRMCisUPBEk6VUB9mXxwp0zyxrMe2od5OiVO8RJ"

# Keyword shards. No category-browse endpoint exists, so this list stands in
# for a taxonomy walk - weighted toward general grocery breadth plus the
# deep-leaf targets this source was onboarded for (minyak goreng / minyak
# kelapa = COICOP 01.1.5.1.2 palm & specialty cooking oil).
_KEYWORDS = [
    "minyak-goreng",
    "minyak-kelapa",
    "santan",
    "margarin",
    "mentega",
    "beras",
    "tepung",
    "gula",
    "garam",
    "bumbu-dapur",
    "kecap",
    "saus",
    "mie-instan",
    "sereal",
    "roti",
    "susu",
    "telur",
    "keju",
    "yogurt",
    "kopi",
    "teh",
    "air-mineral",
    "minuman",
    "sirup",
    "jus",
    "sarden",
    "kornet",
    "abon",
    "ikan-asin",
    "teri",
    "terasi",
    "snack",
    "keripik",
    "biskuit",
    "permen",
    "cokelat",
    "kacang",
    "sabun",
    "sampo",
    "pasta-gigi",
    "deterjen",
    "tisu",
    "popok",
    "pembalut",
    "obat",
    "vitamin",
    "rokok",
    "es-krim",
    "sayur-beku",
]


class AlfagiftSpider(scrapy.Spider):
    name = "alfagift"
    allowed_domains = ["webcommerce-gw.alfagift.id"]
    currency = "IDR"
    language = "id"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.8,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    def _headers(self):
        return {
            "Accept": "application/json",
            "Accept-Language": "id",
            "Referer": "https://alfagift.id/",
            "DeviceType": "Web",
            "DeviceModel": "chrome",
            "Fingerprint": _FINGERPRINT,
            "TrxId": str(random.randint(1_000_000_000, 9_999_999_999)),
            "Latitude": "0",
            "Longitude": "0",
        }

    async def start(self):
        for keyword in _KEYWORDS:
            yield scrapy.Request(
                f"{_SEARCH}?keyword={keyword}&start=0&limit={_PAGE_CAP}",
                callback=self.parse_search,
                headers=self._headers(),
                meta={"keyword": keyword},
                errback=self.errback,
            )

    def parse_search(self, response):
        keyword = response.meta["keyword"]
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("alfagift: non-JSON response for keyword %s", keyword)
            return

        products = payload.get("products") or []
        total = payload.get("totalData") or 0
        if total > _PAGE_CAP:
            logger.warning(
                "alfagift: keyword=%s totalData=%d exceeds cap %d - %d rows missed "
                "(search endpoint does not support paging past start=0)",
                keyword,
                total,
                _PAGE_CAP,
                total - _PAGE_CAP,
            )

        scraped_at = datetime.now(timezone.utc).isoformat()
        for it in products:
            name = it.get("productName")
            price = it.get("finalPrice")
            if not name or price is None:
                continue
            category = (
                " > ".join(
                    p
                    for p in (
                        it.get("categoryNameLvl0"),
                        it.get("categoryNameLvl1"),
                        it.get("categoryNameLvl2"),
                    )
                    if p
                )
                or None
            )
            product_id = it.get("sku") or it.get("plu") or str(it.get("productId", ""))
            yield {
                "product_id": product_id,
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": category,
                "url": f"https://alfagift.id/product/{it.get('productId')}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

    def errback(self, failure):
        logger.error(
            "alfagift: request failed %s - %r", failure.request.url, failure.value
        )

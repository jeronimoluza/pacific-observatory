"""
S-kaupat — https://www.s-kaupat.fi/ (S Group, Finland's largest online grocery).

Next.js app; the storefront's own product/category pages are client-fetched
(no product markup in the raw HTML). Found the real backend via a
Playwright network trace of a live search: `api.s-kaupat.fi` is an Apollo
GraphQL endpoint using persisted queries (GET with a `sha256Hash`, not a
POST with query text) -- both used here are already registered
server-side, so this spider never needs to send GraphQL query text at all,
just the hash + variables. Verified live 2026-09-06 with curl_cffi
impersonate=chrome124: 200, no auth/session needed.

Two things found by probing, not by reading docs:
  1. The `RemoteFilteredProducts` operation (hash
     85a4eed2f0a1e3269ac49b94276ca952922568369d85ddd5dcee34481e4c0f91) is
     wired for keyword search (`queryString: "banaani"`), but it ALSO
     accepts a bare `slug` variable (a category path, e.g.
     "hedelmat-ja-vihannekset") with `queryString: ""` -- this is what
     lets the whole catalogue be walked category-by-category rather than
     needing a keyword per request. `queryString` must still be present
     (empty string), or the API 400s asking for the required variable.
  2. Pagination is a plain `from`/`limit` offset pair -- confirmed
     genuinely distinct product ids between from=0 and from=24 on the
     same category, zero overlap.

31 top-level category slugs come from the storefront nav
(https://www.s-kaupat.fi/tuotteet lists them as /tuotteet/<slug> links);
each is queried directly as a GraphQL category filter, no need to fetch
the HTML nav page at runtime since the slug list is stable and short.

storeId="513971200" is the site's own default store (Helsinki-area S
Group store) -- prices are single-store, not a national average (GOTCHA:
"Finnish-only interface" from the triage sheet was about the UI language,
not about multi-store pricing; this spider inherits the same one-store
scope as the default web UI).

price is a plain EUR float (`product.price`); `product.ean` is the GTIN
barcode, used as product_id since it is stable and globally unique unlike
the internal `sokId`. category comes from `hierarchyPath[0].name` (deepest
node), which is Finnish free text -- adequate since COICOP tagging happens
downstream in the classifier from product_name.
"""

import json
import logging
import urllib.parse as up
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

API_URL = "https://api.s-kaupat.fi/"
STORE_ID = "513971200"
_QUERY_HASH = "85a4eed2f0a1e3269ac49b94276ca952922568369d85ddd5dcee34481e4c0f91"
PAGE_SIZE = 48

_TOP_CATEGORIES = [
    "alkoholi-ja-virvoitusjuomat",
    "hedelmat-ja-vihannekset",
    "hillot-ja-sailykkeet",
    "juustot-tofut-ja-kasvipohjaiset",
    "kahvit-teet-ja-mehut",
    "kala-ja-merenelavat",
    "karkit-suklaat-ja-keksit",
    "kasvipohjaiset-tuotteet",
    "keittio-ja-kattaus",
    "kodinhoito-ja-taloustarvikkeet",
    "kosmetiikka-ja-hygienia",
    "kuivatuotteet-ja-leivonta",
    "kukat-ja-koti",
    "lapset",
    "leivat-ja-leivonnaiset",
    "lemmikit",
    "liha-ja-kasviproteiinit",
    "maito-munat-ja-rasvat",
    "oljyt-maustaminen-ja-kastikkeet",
    "pakasteet",
    "pastat-riisit-ja-nuudelit",
    "ruokatori",
    "snacksit",
    "texmex-ja-maailman-makuja",
    "urheiluravinteet-terveys-ja-itsehoito",
    "valmisruoka",
    "vapaa-aika",
]


def _api_url(slug: str, frm: int) -> str:
    variables = {
        "facets": [],
        "fetchSponsoredContent": False,
        "limit": PAGE_SIZE,
        "queryString": "",
        "slug": slug,
        "storeId": STORE_ID,
        "from": frm,
    }
    extensions = {
        "clientLibrary": {"name": "@apollo/client", "version": "4.2.12"},
        "persistedQuery": {"version": 1, "sha256Hash": _QUERY_HASH},
    }
    qs = up.urlencode(
        {
            "operationName": "RemoteFilteredProducts",
            "variables": json.dumps(variables, separators=(",", ":")),
            "extensions": json.dumps(extensions, separators=(",", ":")),
        }
    )
    return f"{API_URL}?{qs}"


class SKaupatFiSpider(scrapy.Spider):
    name = "s_kaupat_fi"
    allowed_domains = ["s-kaupat.fi"]
    currency = "EUR"
    language = "fi"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for slug in _TOP_CATEGORIES:
            yield scrapy.Request(
                _api_url(slug, 0),
                callback=self.parse_page,
                meta={"slug": slug, "from": 0},
                errback=self.errback,
            )

    def parse_page(self, response):
        slug = response.meta["slug"]
        frm = response.meta["from"]
        try:
            data = json.loads(response.text)
        except ValueError:
            logger.warning(f"{self.name}: bad JSON for slug={slug} from={frm}")
            return

        products = (data.get("data") or {}).get("store", {}).get("products") or {}
        total = products.get("total", 0)
        items = products.get("productListItems") or []
        scraped_at = datetime.now(timezone.utc).isoformat()
        found = 0

        for it in items:
            p = it.get("product") or {}
            product_id = p.get("ean") or p.get("id")
            name = p.get("name")
            price = p.get("price")
            if not product_id or not name or price is None:
                continue

            hierarchy = p.get("hierarchyPath") or []
            category = hierarchy[0].get("name") if hierarchy else slug

            found += 1
            yield {
                "product_id": str(product_id),
                "product_name": str(name).strip()[:500],
                "category": category,
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": f"https://www.s-kaupat.fi/tuote/{p.get('slug', '')}/{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        logger.info(
            f"{self.name}: slug={slug} from={frm} items={len(items)} yielded={found} total={total}"
        )

        next_from = frm + PAGE_SIZE
        if items and next_from < total:
            yield scrapy.Request(
                _api_url(slug, next_from),
                callback=self.parse_page,
                meta={"slug": slug, "from": next_from},
                errback=self.errback,
            )

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
